"""Does a manifest row describe the bytes it stored? And can a historical row
that did not be repaired from evidence rather than from convenience?

THE DEFECT THIS CLOSES

`capture_vintage._persist` supports a `reduce` durability: the upstream file is
fetched, a handful of columns (and for `depth_charts` the newest `dt` slice
only) are written to `nfl/vintage`, and the full file is left in the gitignored
ephemeral store. The manifest row recorded `sha256`, `n_bytes` and `n_lines` --
all three of the UPSTREAM file. The object those fields described was never
persisted. The object that was persisted carried no digest at all.

Measured on the manifest at HEAD 837d52f: **368 of 1,061 PASS rows (34.7%)**,
every `depth_charts` and `weekly_rosters` capture without exception, behind 13
distinct blobs. `coverage._blob_ok` re-hashes the blob, compares it to
`value.sha256`, and correctly returns `RAW_SHA256_MISMATCH` on all 368, so the
rows self-exclude from discharge. Nothing was corrupt and nothing was lost;
a claim was made about the wrong object.

This is the project's dominant defect class wearing provenance clothes: a
reduction step whose output was never checked against the claim made about its
input.

WHAT IS AND IS NOT REPAIRABLE, AND THE LINE BETWEEN THEM

Going forward `_persist` records `persisted_content_sha256` beside
`upstream_content_sha256` and verifies the retained bytes at write time, so new
rows self-verify by construction.

Backwards, the honest answer is not uniform and must not be made to look
uniform. A historical row may be repaired ONLY where the raw upstream bytes
still exist and lawfully reconstruct the reduced form:

    manifest declares upstream sha256
      -> a retained raw file hashes to exactly that
      -> `_reduce_frame` over those bytes produces the stored blob EXACTLY

That chain closes. It establishes both that the blob is the faithful reduction
of an attested input and what its digest is. Seven full-byte files survive in
the gitignored `nfl_vintage/raw/`, and all seven close it.

Where the chain does not close, the row STAYS UNVERIFIABLE and says so. Hashing
the blob on disk and writing the result into the row would make every row
self-consistent and prove nothing: it attests that the file has not changed
since the moment we looked, which is not the question. That digest is still
recorded, because a tamper baseline from today forward is worth having -- under
a name that cannot be read as verification, and without moving the row's state.

WHAT THIS MODULE DOES NOT DO

It does not rewrite `nfl/vintage_manifest.jsonl`. The manifest is append-only
and its historical rows are the record of what was believed at the time;
overwriting them would destroy the evidence that the defect existed. The
recovery is a SIDECAR, joined on the blob path, and the original row remains
intact and recoverable.
"""
from __future__ import annotations

import datetime as _dt
import gzip
import hashlib
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from nfl.capture import registry as _registry  # noqa: E402

MANIFEST = _REPO / "nfl" / "vintage_manifest.jsonl"
RECOVERY = _REPO / "nfl" / "vintage_provenance_recovery.jsonl"
EPHEMERAL_RAW = _REPO / "nfl_vintage" / "raw"

SCHEMA_VERSION = "persisted-provenance-1"

# States a persisted artifact can be in. Four, not two, for the same reason M0
# status is four states and not a boolean: "we can verify this" and "this is
# intact" are different claims and collapsing them throws away the distinction
# that decides what may be said about the artifact.
VERIFIED_AT_CAPTURE = "VERIFIED_AT_CAPTURE"
RECONSTRUCTED_AND_VERIFIED = "RECONSTRUCTED_AND_VERIFIED"
UNVERIFIABLE_NO_RETAINED_RAW = "UNVERIFIABLE_NO_RETAINED_RAW"
UNVERIFIABLE_BLOB_ABSENT = "UNVERIFIABLE_BLOB_ABSENT"


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _reducers():
    return {s.name: tuple(s.reduce_cols)
            for s in _registry.REGISTRY if s.durability == "reduce"}


def _load_reduce_frame():
    """`_reduce_frame` and the transform identity, loaded from the capture tool.

    Imported by path because `nfl/tools` is a script directory, not a package.
    The transformation that recovers a historical digest MUST be the same
    function that writes a new one -- two copies of a reduction is how the
    digests would drift apart again.
    """
    import importlib.machinery, importlib.util
    path = _REPO / "nfl" / "tools" / "capture_vintage.py"
    loader = importlib.machinery.SourceFileLoader("_cv_for_provenance", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = mod
    loader.exec_module(mod)
    return mod


def resolve_blob(blob: str):
    """The path a manifest row's `blob` actually names, or None.

    Two rows written at `20260906T201020Z` name `...reduced.csv` when only
    `...reduced.csv.gz` exists (WS13 §3c). A naive existence check reports them
    absent, which overstates the damage; the resolution is recorded rather than
    silently applied.
    """
    p = _REPO / blob
    if p.exists():
        return p, "as_written"
    gz = _REPO / (blob + ".gz")
    if gz.exists():
        return gz, "gz_suffix_appended"
    return None, "unresolvable"


def read_blob(path: pathlib.Path) -> bytes:
    if str(path).endswith(".gz"):
        with gzip.open(path, "rb") as fh:
            return fh.read()
    return path.read_bytes()


def reduce_rows(manifest_path=MANIFEST) -> Outcome:
    """Every PASS row whose durability is `reduce`, grouped by cited blob."""
    path = pathlib.Path(manifest_path)
    if not path.exists():
        return Outcome.blocked(
            "MANIFEST_ABSENT", f"{path} does not exist",
            cause=Cause.DEPENDENCY)
    by_blob, n_rows = {}, 0
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("state") != "PASS":
            continue
        val = row.get("value") or {}
        if val.get("durability") != "reduce":
            continue
        n_rows += 1
        by_blob.setdefault(val.get("blob") or "", []).append(row)
    if n_rows == 0:
        # Zeros are errors, not results. A manifest with no reduce rows in a
        # repository whose whole defect is reduce rows means the wrong file was
        # read, not that the defect is gone.
        return Outcome.fail(
            "NO_REDUCE_ROWS_FOUND",
            f"{path} carries no PASS row with durability 'reduce'. The "
            f"measured population at HEAD 837d52f is 368 such rows; reading "
            f"zero means this is not that manifest.")
    return Outcome.ok("REDUCE_ROWS", value=by_blob, n_rows=n_rows,
                      n_distinct_blobs=len(by_blob))


def defect_rows(manifest_path=MANIFEST) -> Outcome:
    """The HISTORICAL defect population: reduce PASS rows with no persisted
    digest. Grouped by cited blob, same shape as `reduce_rows`.

    WHY A SEPARATE FUNCTION, AND WHY IT IS DEFINED BY SHAPE RATHER THAN BY A
    DATE OR A COUNT.

    The defect population is 368 rows and every statement made about it -- 366
    by hash mismatch, 2 by a missing .gz suffix, 216 recoverable, 152
    unverifiable -- is measured against that number. Those statements were
    checked against `reduce_rows()`, which returns EVERY reduce row in an
    append-only manifest that grows every time a capture runs. So the first
    legitimate capture after the repair moved 368 to 370 and turned four
    frozen historical measurements into failures, which is the "a count in
    prose goes stale the moment it is written" defect occurring inside the
    measurement system.

    A cutoff timestamp would have been the wrong fix: it would need updating
    too, and it would silently include any future row written by an older code
    path. The population is defined by the property that CONSTITUTES the
    defect -- a reduce row carrying no digest of the bytes it persisted -- so
    it is closed by construction. Every row written after the repair carries
    one, `_assert_no_pass_without_capture` refuses to append one that does not,
    and the set can therefore never grow again.
    """
    out = reduce_rows(manifest_path)
    if out.state is not State.PASS:
        return out
    by_blob, n = {}, 0
    for blob, rows in out.value.items():
        keep = [r for r in rows
                if not (r.get("value") or {}).get("persisted_content_sha256")]
        if keep:
            by_blob[blob] = keep
            n += len(keep)
    if n == 0:
        return Outcome.fail(
            "NO_DEFECT_ROWS_FOUND",
            f"{manifest_path} carries no reduce PASS row lacking a persisted "
            f"digest. The measured historical population is 368; reading zero "
            f"means this is not that manifest, not that the history changed.")
    return Outcome.ok("DEFECT_ROWS", value=by_blob, n_rows=n,
                      n_distinct_blobs=len(by_blob),
                      n_reduce_rows_total=out.evidence["n_rows"],
                      definition="reduce PASS rows with no "
                                 "persisted_content_sha256")


def attempt_recovery(blob: str, rows: list, cv) -> dict:
    """Try to close the verification chain for ONE persisted blob.

    Returns a record, never a bare digest. A digest with no statement of how it
    was obtained is exactly the artifact that caused this defect.
    """
    cols = _reducers()
    upstream = sorted({(r.get("value") or {}).get("sha256") or "" for r in rows})
    source = sorted({r.get("source") for r in rows})
    rec = {
        "schema_version": SCHEMA_VERSION,
        "blob": blob,
        "source": source[0] if len(source) == 1 else source,
        "n_manifest_rows_covered": len(rows),
        "capture_ids": sorted({r.get("capture_id") for r in rows}),
        "upstream_content_sha256": upstream[0] if len(upstream) == 1 else upstream,
        "persisted_content_sha256": None,
        "verification_state": None,
        "recovery_method": None,
        "recovered_from": None,
        "recovered_at_utc": _now(),
        "manifest_row_rewritten": False,
        "original_manifest_row_intact": True,
    }

    # WHICH MACHINE LOOKED, AND WHY IT DECIDES WHETHER THE RAW BYTES SURVIVED.
    #
    # WS-L established the mechanism and it reproduces here with no exceptions:
    # every digest observed ONLY by a GitHub-Actions run lost its upstream
    # bytes, and every digest seen at least once by a non-Actions executor kept
    # them. `nfl_vintage/raw/` is gitignored and Actions runners are ephemeral,
    # so the raw store never leaves the runner. Raw retention is therefore a
    # property of WHICH MACHINE HAPPENED TO LOOK, not of the source, the date
    # or the durability -- which is why the split below is 6 lost / 7 kept and
    # not a scatter. Recorded per blob so the recovery artifact carries the
    # cause and not only the outcome.
    execs = set()
    for r in rows:
        e = ((r.get("value") or {}).get("execution_target") or {}).get(
            "executor") or {}
        execs.add("GITHUB_ACTIONS" if e.get("is_github_actions")
                  else "NON_ACTIONS")
    rec["observed_by_executors"] = sorted(execs)
    rec["observed_on_dates"] = sorted({str(r.get("capture_id"))[:8]
                                       for r in rows})
    rec["actions_only"] = execs == {"GITHUB_ACTIONS"}

    path, how = resolve_blob(blob)
    rec["blob_resolved_as"] = how
    if path is None:
        rec["verification_state"] = UNVERIFIABLE_BLOB_ABSENT
        rec["recovery_method"] = "NONE_BLOB_NOT_ON_DISK"
        rec["why_unverifiable"] = (
            f"the cited path {blob} resolves to nothing, with or without a .gz "
            f"suffix. There are no bytes to hash and none to reconstruct.")
        return rec
    rec["blob_path_on_disk"] = str(path.relative_to(_REPO))

    stored = read_blob(path)
    stored_sha = hashlib.sha256(stored).hexdigest()
    # NAMED SO IT CANNOT BE MISREAD. This is the digest of whatever is on disk
    # today. It attests nothing about faithfulness to upstream -- it is a
    # tamper baseline from this date forward, and it never sets
    # verification_state.
    rec["unattested_blob_digest_at_migration"] = stored_sha
    rec["unattested_blob_digest_attests"] = (
        "that these bytes have not changed since 2026-09-14. NOT that they are "
        "a faithful reduction of the upstream file the row names. Trust-on-"
        "first-use, recorded as such.")
    rec["blob_file_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    rec["persisted_n_bytes"] = len(stored)

    up = rec["upstream_content_sha256"]
    src = rec["source"]
    if not isinstance(up, str) or not isinstance(src, str) or src not in cols:
        rec["verification_state"] = UNVERIFIABLE_NO_RETAINED_RAW
        rec["recovery_method"] = "NONE_ROW_NOT_SINGLE_VALUED"
        rec["why_unverifiable"] = (
            "the rows citing this blob do not agree on a single source or a "
            "single upstream digest, so there is no one input to reconstruct "
            "from.")
        return rec

    raw = EPHEMERAL_RAW / f"{src}.{up[:16]}.csv"
    if not raw.exists():
        rec["verification_state"] = UNVERIFIABLE_NO_RETAINED_RAW
        rec["recovery_method"] = "NONE_UPSTREAM_BYTES_NOT_RETAINED"
        rec["raw_looked_for"] = str(raw.relative_to(_REPO))
        rec["why_unverifiable"] = (
            f"the upstream file {src}.{up[:16]}.csv is not in the gitignored "
            f"ephemeral store, and this executor has no egress, so it cannot "
            f"be re-fetched. Even with egress a re-fetch would return TODAY's "
            f"file: nflverse restamps these continuously, so the bytes that "
            f"hash to {up[:16]} are not obtainable from the origin any more. "
            f"The reduction is irreversible -- columns and, for depth_charts, "
            f"every prior dt slice were discarded -- so the blob cannot "
            f"reconstruct its own input either. Permanently unverifiable.")
        rec["loss_mechanism"] = (
            "RAW_STORE_IS_GITIGNORED_AND_THE_EXECUTOR_WAS_EPHEMERAL"
            if rec["actions_only"] else "RAW_BYTES_NOT_PRESENT_CAUSE_UNKNOWN")
        rec["loss_mechanism_detail"] = (
            "every capture of this vintage ran on a GitHub-Actions runner, and "
            "nfl_vintage/raw/ is gitignored, so the upstream bytes were "
            "discarded with the runner. Reproduced across all 13 reduce "
            "vintages with no exceptions: 6 of 6 Actions-only lost their raw, "
            "7 of 7 seen at least once from a non-Actions executor kept it. "
            "This is WS-L RL-9 -- an artifact whose only home is an untracked "
            "store -- and it is the cause of this row being unverifiable, not "
            "a coincidence beside it."
            if rec["actions_only"] else
            "this vintage was observed from a non-Actions executor, so the "
            "usual ephemeral-runner explanation does not apply and the absence "
            "has some other cause. Flagged as not understood rather than "
            "assigned to the mechanism that fits the other rows.")
        return rec

    payload = raw.read_bytes()
    raw_sha = hashlib.sha256(payload).hexdigest()
    rec["raw_recovered_from"] = str(raw.relative_to(_REPO))
    rec["raw_sha256"] = raw_sha
    if raw_sha != up:
        # The retained file does not attest to the row. It is not evidence,
        # and using it anyway would be the backfill this module refuses.
        rec["verification_state"] = UNVERIFIABLE_NO_RETAINED_RAW
        rec["recovery_method"] = "NONE_RETAINED_RAW_DOES_NOT_MATCH_ROW"
        rec["why_unverifiable"] = (
            f"a file with the right name exists but hashes to {raw_sha[:16]}, "
            f"not the {up[:16]} the manifest declares. It is some other "
            f"vintage and attests nothing about this row.")
        return rec

    rebuilt, detail = cv._reduce_frame(payload, cols[src])
    rebuilt_sha = hashlib.sha256(rebuilt).hexdigest()
    if rebuilt_sha != stored_sha:
        rec["verification_state"] = UNVERIFIABLE_NO_RETAINED_RAW
        rec["recovery_method"] = "NONE_RECONSTRUCTION_DID_NOT_MATCH"
        rec["reconstructed_sha256"] = rebuilt_sha
        rec["why_unverifiable"] = (
            f"the upstream bytes are attested, but reducing them produces "
            f"{rebuilt_sha[:16]} and the stored blob is {stored_sha[:16]}. The "
            f"stored artifact is NOT this transformation of this input. That "
            f"is a stronger finding than 'unverifiable' and must be "
            f"investigated, not recorded as a recovery.")
        return rec

    rec["persisted_content_sha256"] = rebuilt_sha
    rec["verification_state"] = RECONSTRUCTED_AND_VERIFIED
    rec["recovery_method"] = "RECONSTRUCTED_FROM_RETAINED_UPSTREAM_BYTES"
    rec["recovered_from"] = str(raw.relative_to(_REPO))
    rec["recovery_chain"] = [
        f"manifest row declares upstream sha256 = {up}",
        f"retained raw {raw.name} hashes to exactly that digest",
        f"_reduce_frame over those bytes yields {rebuilt_sha}",
        f"the stored blob's uncompressed bytes hash to {stored_sha}",
        "the two are equal, so the blob is the faithful reduction of an "
        "attested input and its digest is established, not assumed",
    ]
    rec["recovery_caveat"] = (
        "the transformation run here is TODAY's code. That is sufficient and "
        "the reason is worth stating: a byte-exact match proves the stored "
        "blob IS this reduction of the attested input, whatever code first "
        "produced it. It does not prove the historical code was identical, and "
        "nothing here claims it was.")
    rec["transformation"] = {
        "transform_id": cv.TRANSFORM_ID,
        "transform_version": cv.TRANSFORM_VERSION,
        "code_sha256": cv._transform_code_identity(),
        "code_symbol": "nfl.tools.capture_vintage._reduce_frame",
        "input_sha256": up,
        "input_n_bytes": len(payload),
        "output_sha256": rebuilt_sha,
        "output_n_bytes": len(rebuilt),
        "output_columns": detail["selected_columns"],
        "requested_columns": detail["requested_columns"],
        "missing_columns": detail["missing_columns"],
        "row_filter": "newest_dt_slice" if detail["newest_dt"] else "no_row_filter",
        "row_filter_value": detail["newest_dt"],
        "rows_in_file": detail["rows_in_file"],
        "rows_kept": detail["rows_kept"],
        "deterministic": True,
        "reversible": False,
    }
    return rec


def build_recovery(manifest_path=MANIFEST, out_path=RECOVERY) -> Outcome:
    """Attempt recovery for every reduce blob and write the sidecar."""
    ro = reduce_rows(manifest_path)
    if ro.state is not State.PASS:
        return ro
    by_blob = ro.value
    cv = _load_reduce_frame()

    recs = [attempt_recovery(b, rows, cv) for b, rows in sorted(by_blob.items())]
    if not recs:
        return Outcome.fail(
            "RECOVERY_PRODUCED_NO_RECORDS",
            "reduce rows were found but no recovery record was built.")

    tally, rowtally = {}, {}
    for r in recs:
        tally[r["verification_state"]] = tally.get(r["verification_state"], 0) + 1
        rowtally[r["verification_state"]] = (
            rowtally.get(r["verification_state"], 0) + r["n_manifest_rows_covered"])

    header = {
        "schema_version": SCHEMA_VERSION,
        "record_kind": "header",
        "written_at_utc": _now(),
        "written_by": "nfl/capture/persisted_provenance.py",
        "joins_to": "nfl/vintage_manifest.jsonl on value.blob",
        "manifest_rewritten": False,
        "why_a_sidecar": (
            "the manifest is append-only and its rows are the record of what "
            "was believed when they were written. Overwriting them would erase "
            "the evidence that the defect existed. This file is additive and "
            "the original rows stay intact and recoverable."),
        "n_reduce_pass_rows": ro.evidence["n_rows"],
        "n_distinct_blobs": len(recs),
        "blobs_by_state": tally,
        "manifest_rows_by_state": rowtally,
    }
    out = pathlib.Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as fh:
        fh.write(json.dumps(header, sort_keys=True) + "\n")
        for r in recs:
            fh.write(json.dumps(r, sort_keys=True) + "\n")
    return Outcome.ok("RECOVERY_WRITTEN", value=header,
                      path=str(out.relative_to(_REPO)),
                      blobs_by_state=tally, manifest_rows_by_state=rowtally)


def load_recovery(path=RECOVERY) -> dict:
    """blob path -> recovery record. Empty dict if the sidecar is absent."""
    p = pathlib.Path(path)
    if not p.exists():
        return {}
    out = {}
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        if rec.get("record_kind") == "header":
            continue
        out[rec["blob"]] = rec
    return out


def self_verifies(value: dict, recovery=None) -> Outcome:
    """Can a reader holding the blob and this row confirm the row describes it?

    THE ONE QUESTION THIS WHOLE REPAIR EXISTS TO MAKE ANSWERABLE. It is
    deliberately a three-way answer, not a boolean:

      PASS     the row carries a digest of the persisted bytes and it matches
      FAIL     it carries one and it does not match -- a real integrity defect
      BLOCKED  no digest of the persisted bytes exists anywhere for this row

    The third is the historical state, and it is BLOCKED rather than FAIL
    because nothing is known to be wrong with those bytes. They simply cannot
    be checked, which is a different fact and gets a different word.
    """
    value = value or {}
    blob = value.get("blob")
    if not blob:
        return Outcome.blocked(
            "NO_PERSISTED_ARTIFACT", "the row cites no blob.",
            cause=Cause.DEPENDENCY)
    path, how = resolve_blob(blob)
    if path is None:
        return Outcome.fail("PERSISTED_ARTIFACT_MISSING_ON_DISK", blob)

    sha = value.get("persisted_content_sha256")
    provenance = "row"
    if not sha:
        rec = (recovery if recovery is not None else load_recovery()).get(blob)
        if rec and rec.get("persisted_content_sha256"):
            sha = rec["persisted_content_sha256"]
            provenance = f"recovery_sidecar:{rec.get('recovery_method')}"
    if not sha:
        return Outcome.blocked(
            "PERSISTED_DIGEST_ABSENT",
            f"{blob}: no digest covering the bytes actually persisted exists "
            f"in the row or in the recovery sidecar. `sha256` on this row "
            f"describes the upstream file, which was never stored here. The "
            f"artifact is historically unverifiable and is not claimed "
            f"otherwise.",
            cause=Cause.DEPENDENCY, blob=blob,
            upstream_content_sha256=value.get("sha256"))

    got = hashlib.sha256(read_blob(path)).hexdigest()
    if got != sha:
        return Outcome.fail(
            "PERSISTED_CONTENT_SHA256_MISMATCH",
            f"{blob}: bytes hash to {got[:16]}, row/sidecar says {sha[:16]}.",
            blob=blob, expected=sha, got=got, digest_provenance=provenance)
    return Outcome.ok("PERSISTED_ARTIFACT_SELF_VERIFIES",
                      value={"blob": blob, "persisted_content_sha256": sha,
                             "digest_provenance": provenance,
                             "blob_resolved_as": how},
                      detail=f"{blob} verifies against {provenance}")


def main() -> int:
    out = build_recovery()
    print(f"{out.state.value}[{out.code}] {out.detail}")
    if out.state is State.PASS:
        print(json.dumps(out.value, indent=2, sort_keys=True))
    return 0 if out.state is State.PASS else 1


if __name__ == "__main__":
    sys.exit(main())
