#!/usr/bin/env python3.12
"""Enforce owner decision RET-001 against what is actually on disk.

The retention guards in `nfl/capture/availability.py` are pure functions over
before/after state. This is what feeds them the real thing: the blob set and
manifest as they stood before a watch run, and as they stand after.

WHY THIS RUNS SEPARATELY FROM THE UNIT TESTS

The tests prove the guards refuse a seeded violation. They cannot prove that
nothing deleted a vintage on a live runner, because the tests do not touch the
real store. A policy checked only in a fixture is a policy that holds only in
fixtures.

Usage:
    python3.12 nfl/tools/check_retention.py --before-blobs /tmp/b.txt \
        --before-manifest /tmp/m.jsonl
    python3.12 nfl/tools/check_retention.py            # current state only
"""
from __future__ import annotations

import argparse
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import State      # noqa: E402
from nfl.capture import availability as AV               # noqa: E402


def _lines(p: pathlib.Path | None) -> list:
    if p is None or not p.exists():
        return []
    return [ln for ln in p.read_text().splitlines() if ln.strip()]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--before-blobs", default=None,
                    help="file listing blob paths present BEFORE the run")
    ap.add_argument("--before-manifest", default=None,
                    help="copy of the manifest as it stood BEFORE the run")
    ap.add_argument("--blob-root", default=str(AV.BLOB_ROOT))
    ap.add_argument("--manifest", default=str(AV.MANIFEST))
    args = ap.parse_args()

    root = pathlib.Path(args.blob_root)
    after_blobs = {p.name for p in root.glob("*")} if root.exists() else set()
    after_rows = _lines(pathlib.Path(args.manifest))
    before_blobs = {pathlib.Path(x).name for x in
                    _lines(pathlib.Path(args.before_blobs)
                           if args.before_blobs else None)}
    before_rows = _lines(pathlib.Path(args.before_manifest)
                         if args.before_manifest else None)

    print(f"RET-001 retention check")
    print(f"  blobs   before {len(before_blobs):>4}  after {len(after_blobs):>4}")
    print(f"  rows    before {len(before_rows):>4}  after {len(after_rows):>4}")

    checks = [
        ("R4 no vintage deleted",
         AV.assert_no_vintage_deleted(before_blobs, after_blobs)),
        ("R5 manifest append-only",
         AV.assert_manifest_append_only(before_rows, after_rows)),
        ("R8 no orphan blobs",
         AV.assert_no_orphan_blobs(after_blobs, after_rows)),
    ]
    for src in AV.WATCHED:
        checks.append((f"R1/R7 retention policy {src}",
                       AV.assert_retention_policy(src)))

    bad = False
    for label, out in checks:
        print(f"  {out.state.value:<15}{label:<44}{out.code}")
        if out.state is State.FAIL:
            print(f"      {out.detail}")
            bad = True
        elif out.state is State.BLOCKED:
            print(f"      {out.detail}")
            bad = True
    print("  RET-001 " + ("VIOLATED" if bad else "holds"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
