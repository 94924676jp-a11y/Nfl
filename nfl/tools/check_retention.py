#!/usr/bin/env python3.12
"""Enforce owner decision RET-001 against what is actually on disk, in BOTH stores.

The retention guards in `nfl/capture/availability.py` are pure functions over
before/after state. This is what feeds them the real thing: the blob set and
manifest as they stood before a run, and as they stand after.

WHY THIS RUNS SEPARATELY FROM THE UNIT TESTS

The tests prove the guards refuse a seeded violation. They cannot prove that
nothing deleted a vintage on a live runner, because the tests do not touch the
real store. A policy checked only in a fixture is a policy that holds only in
fixtures.

WS13 W7 -- THE SCOPE DEFECT THIS VERSION REPAIRS

Until 2026-09-14 this tool was pointed at `availability.BLOB_ROOT` and
`availability.MANIFEST` and nothing else. That store is 2 blobs and 6 rows. The
VINTAGE store -- 490 blobs, 1,672 rows, every perishable official capture the
project owns -- was outside its scope entirely, and its own output said so:
`blobs before 0 after 2 - rows before 0 after 6`.

The consequence is measured, not hypothetical. On 2026-09-08/09/10, fifty
GitHub-Actions capture runs committed a blob and appended ZERO manifest rows,
leaving 48 orphan `schedules.*.csv.gz` files in `nfl/vintage/`. Throughout that
period `R8 NO_ORPHAN_BLOBS` reported PASS. It was not wrong about what it
checked; it was checking a different directory. A guard whose name reads wider
than its scope is a guard that produces false assurance, which is worse than no
guard at all.

THE VINTAGE MANIFEST NESTS ITS BLOB PATHS, AND A NAIVE READER FINDS 447 ORPHANS

`availability.assert_no_orphan_blobs` reads `row['blob']` and
`row['blob_sidecar']` at the TOP level. Vintage rows carry the path at
`value.blob`, and delivery rows carry a LIST at
`value.delivery.raw_evidence_blobs` (WS13 section 3e names this exact trap:
`delivered_injury_evidence.df1dd90380b8d720.html.gz` is referenced from nowhere
else and any scan reading only `value.blob` reports it as an orphan). So this
module carries its own vintage-aware collector, and then CROSS-CHECKS it: a
recursive scan finds every string anywhere in the row that names a path in the
blob directory, and if the explicit collector missed one the tool REFUSES with
a named error instead of reporting a false orphan. Measured 2026-09-14:
explicit 448 names, recursive 445, difference 0 missed, 48 genuine orphans --
the same 48 WS13 counted.

STANDING LOSS AND RECURRENCE ARE DIFFERENT QUESTIONS AND ARE GATED DIFFERENTLY

The 48 orphans are recorded, unrecoverable loss (WS13 section 9.1). Gating every
future run on them leaves exactly two moves, and both are wrong: delete the
orphan blobs, which destroys evidence, or switch the check off, which is how
guards die. So:

  * the STANDING census (R8) is always computed and always printed. It is not
    suppressed, not rounded away, and not marked green.
  * the DELTA gates (R4, R5, R9, R10) are what a capture run is gated on. They
    ask whether THIS run introduced the defect, which is the question a run can
    answer and the one that prevents recurrence.

`--gate delta` selects the second set for the exit code. It is not a loosened
threshold: nothing that was failing is now passing, and the standing failure is
still printed in full on every run.

Usage:
    python3.12 nfl/tools/check_retention.py                      # both stores
    python3.12 nfl/tools/check_retention.py --store vintage
    python3.12 nfl/tools/check_retention.py --store vintage --snapshot-to /tmp/before
    python3.12 nfl/tools/check_retention.py --store vintage --gate delta \
        --before-blobs /tmp/before.blobs --before-manifest /tmp/before.manifest
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from nfl.capture import availability as AV                           # noqa: E402

# The two stores, named rather than assumed. `availability` is the watch-only
# store; `vintage` is the perishable-capture store the T-90 obligations are
# discharged from.
STORES = {
    "availability": {"blob_root": AV.BLOB_ROOT, "manifest": AV.MANIFEST,
                     "glob": "*"},
    "vintage": {"blob_root": _REPO / "nfl" / "vintage",
                "manifest": _REPO / "nfl" / "vintage_manifest.jsonl",
                "glob": "*"},
}

# Keys that legitimately hold a blob path in a manifest row, at whatever nesting
# the writer used. Listed explicitly so that adding a writer is a reviewable
# edit rather than something a recursive scan absorbs silently.
_BLOB_KEYS = ("blob", "blob_sidecar")
_BLOB_LIST_PATHS = (("value", "delivery", "raw_evidence_blobs"),)


def _lines(p: "pathlib.Path | None") -> list:
    if p is None or not p.exists():
        return []
    return [ln for ln in p.read_text().splitlines() if ln.strip()]


def _explicit_blob_names(row: dict) -> set:
    """Blob file names this row names, read from the declared locations."""
    out = set()
    for holder in (row, row.get("value") if isinstance(row.get("value"), dict)
                   else None):
        if not isinstance(holder, dict):
            continue
        for k in _BLOB_KEYS:
            v = holder.get(k)
            if isinstance(v, str) and v:
                out.add(pathlib.Path(v).name)
    for path in _BLOB_LIST_PATHS:
        node = row
        for seg in path:
            node = node.get(seg) if isinstance(node, dict) else None
            if node is None:
                break
        if isinstance(node, list):
            for v in node:
                if isinstance(v, str) and v:
                    out.add(pathlib.Path(v).name)
    return out


def _recursive_blob_names(node, marker: str, acc: set) -> set:
    """Every string ANYWHERE in the row that names a path inside the store.

    This is not the collector. It is the audit of the collector: if it finds a
    name the explicit collector missed, the explicit collector is out of date
    and the tool must say so rather than report that blob as an orphan.
    """
    if isinstance(node, str):
        if marker in node:
            acc.add(pathlib.Path(node).name)
    elif isinstance(node, dict):
        for v in node.values():
            _recursive_blob_names(v, marker, acc)
    elif isinstance(node, list):
        for v in node:
            _recursive_blob_names(v, marker, acc)
    return acc


def named_blobs(manifest_lines: list, marker: str) -> Outcome:
    """Blob names the manifest accounts for, with the collector audited.

    Refuses rather than guesses. A row this cannot parse is counted and named:
    an unparseable row is not zero blobs, it is an unknown number of them, and
    treating the two the same is how an orphan census understates itself.
    """
    explicit, recursive, unparseable = set(), set(), 0
    for ln in manifest_lines:
        try:
            row = json.loads(ln)
        except ValueError:
            unparseable += 1
            continue
        if not isinstance(row, dict):
            unparseable += 1
            continue
        explicit |= _explicit_blob_names(row)
        _recursive_blob_names(row, marker, recursive)
    missed = sorted(recursive - explicit)
    if missed:
        return Outcome.blocked(
            "BLOB_REFERENCE_LOCATION_UNKNOWN",
            f"{len(missed)} blob path(s) appear in manifest rows at a location "
            f"this tool's explicit collector does not read: {missed[:5]}. A "
            f"writer has added a new nesting for blob references. Reporting "
            f"these as orphans would be a false positive and skipping them "
            f"would be silence, so the census refuses until the collector is "
            f"extended.",
            cause=Cause.DATA, missed=missed[:20], n_missed=len(missed))
    if unparseable:
        return Outcome.blocked(
            "MANIFEST_ROW_UNPARSEABLE",
            f"{unparseable} manifest line(s) are not JSON objects. The set of "
            f"blobs they name is unknown, so no orphan count computed over the "
            f"remainder is trustworthy.",
            cause=Cause.DATA, n_unparseable=unparseable)
    return Outcome.ok("BLOB_NAMES_READ", value=explicit,
                      detail=f"{len(explicit)} distinct blob name(s) named by "
                             f"{len(manifest_lines)} manifest row(s); "
                             f"recursive audit found {len(recursive)} and "
                             f"missed none",
                      n_explicit=len(explicit), n_recursive=len(recursive))


def assert_no_orphan_blobs_scoped(blob_names, manifest_lines, marker) -> Outcome:
    """R8, standing census, for a store whose rows nest their blob paths."""
    named = named_blobs(manifest_lines, marker)
    if named.state is not State.PASS:
        return named
    orphans = sorted(set(blob_names) - named.value)
    if orphans:
        return Outcome.fail(
            "ORPHAN_BLOB_NOT_FROM_AN_OBSERVATION",
            f"{len(orphans)} file(s) in the store are named by no manifest "
            f"row: {orphans[:5]}{' ...' if len(orphans) > 5 else ''}. Bytes "
            f"that no recorded observation produced are not capture evidence, "
            f"whatever directory they sit in.",
            n_orphans=len(orphans), orphans=orphans[:20])
    return Outcome.ok("NO_ORPHAN_BLOBS", value=len(named.value),
                      detail="every stored blob is named by an observation")


def assert_no_new_orphan(before_blobs, after_blobs, manifest_lines,
                         marker) -> Outcome:
    """R9. THIS RUN did not add a blob that no manifest row names.

    The W3 guard, generalised off the log string. The committed version of this
    invariant lived in the workflow as `grep -qE '^manifest rows appended:
    [1-9]'` -- a check on a line of stdout. The run that lost 2026-09-09
    printed no summary line at all, which is precisely the condition under
    which a stdout guard is least able to see anything. This reads the
    filesystem instead: the blob set before, the blob set after, and the
    manifest as it now stands.
    """
    named = named_blobs(manifest_lines, marker)
    if named.state is not State.PASS:
        return named
    added = set(after_blobs) - set(before_blobs)
    new_orphans = sorted(added - named.value)
    if new_orphans:
        return Outcome.fail(
            "BLOB_WRITTEN_WITHOUT_MANIFEST_ROW",
            f"this run added {len(added)} blob(s) and {len(new_orphans)} of "
            f"them are named by no manifest row: {new_orphans[:5]}. Durable "
            f"bytes with no manifest row are orphans: nothing attributes them "
            f"to a source, a game, a window or a basis, so they can discharge "
            f"nothing and they cannot be told apart from a file dropped in by "
            f"hand.",
            n_added=len(added), n_new_orphans=len(new_orphans),
            new_orphans=new_orphans[:20])
    return Outcome.ok("NO_NEW_ORPHAN_BLOB", value=len(added),
                      detail=f"{len(added)} blob(s) added, every one named by "
                             f"a manifest row")


def assert_rows_accompany_blobs(before_blobs, after_blobs,
                                before_rows, after_rows) -> Outcome:
    """R10. A run that wrote bytes wrote a row. The W3 symptom, named exactly.

    Weaker than R9 and kept beside it on purpose: R10 is the condition the 50
    lost runs actually violated, stated in the same terms the incident is
    recorded in, so a future reader can match the code to the history.
    """
    added_blobs = set(after_blobs) - set(before_blobs)
    added_rows = len(after_rows) - len(before_rows)
    if added_blobs and added_rows <= 0:
        return Outcome.fail(
            "BLOBS_WITHOUT_ANY_MANIFEST_APPEND",
            f"this run added {len(added_blobs)} blob(s) and appended "
            f"{added_rows} manifest row(s). Measured precedent: 50 runs on "
            f"2026-09-08/09/10 did exactly this, and all of 2026-09-09 -- "
            f"including the four runs inside the NE@SEA T-90 inactives window "
            f"-- is absent from the manifest as a result. That evidence is "
            f"not recoverable.",
            n_added_blobs=len(added_blobs), n_added_rows=added_rows,
            added_blobs=sorted(added_blobs)[:20])
    return Outcome.ok("ROWS_ACCOMPANY_BLOBS", value=added_rows,
                      detail=f"{len(added_blobs)} blob(s) added alongside "
                             f"{added_rows} manifest row(s)")


# Which checks gate a capture run. Everything else is printed, never hidden.
_DELTA_CODES = ("R4", "R5", "R9", "R10")


def _store_checks(name: str, before_blobs, after_blobs, before_rows,
                  after_rows, marker) -> list:
    checks = [
        ("R4", "no vintage deleted",
         AV.assert_no_vintage_deleted(before_blobs, after_blobs)),
        ("R5", "manifest append-only",
         AV.assert_manifest_append_only(before_rows, after_rows)),
        ("R8", "no orphan blobs (standing census)",
         assert_no_orphan_blobs_scoped(after_blobs, after_rows, marker)),
        ("R9", "no NEW orphan blob from this run",
         assert_no_new_orphan(before_blobs, after_blobs, after_rows, marker)),
        ("R10", "a run that wrote blobs appended rows",
         assert_rows_accompany_blobs(before_blobs, after_blobs,
                                     before_rows, after_rows)),
    ]
    if name == "availability":
        for src in AV.WATCHED:
            checks.append(("R1/R7", f"retention policy {src}",
                           AV.assert_retention_policy(src)))
    return checks


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--store", default="both",
                    choices=("availability", "vintage", "both"),
                    help="which store to check. DEFAULT CHANGED 2026-09-14 "
                         "from availability-only to both; see WS13 W7.")
    ap.add_argument("--before-blobs", default=None,
                    help="file listing blob paths present BEFORE the run")
    ap.add_argument("--before-manifest", default=None,
                    help="copy of the manifest as it stood BEFORE the run")
    ap.add_argument("--snapshot-to", default=None,
                    help="write PREFIX.blobs and PREFIX.manifest for the "
                         "selected store and exit. Run this BEFORE a capture; "
                         "feed the two files back afterwards.")
    ap.add_argument("--gate", default="all", choices=("all", "delta"),
                    help="which checks decide the exit code. 'delta' gates on "
                         "R4/R5/R9/R10 -- what THIS run did. The standing "
                         "census is printed either way and is never "
                         "suppressed.")
    ap.add_argument("--blob-root", default=None)
    ap.add_argument("--manifest", default=None)
    args = ap.parse_args(argv)

    names = (["availability", "vintage"] if args.store == "both"
             else [args.store])
    if len(names) > 1 and (args.before_blobs or args.before_manifest
                           or args.snapshot_to):
        print("REFUSED: --before-blobs, --before-manifest and --snapshot-to "
              "name ONE store's state. Pass --store availability or "
              "--store vintage with them; a single before-file cannot "
              "describe two stores and pretending it can is how a delta gate "
              "starts measuring the wrong directory.")
        return 2

    if args.snapshot_to:
        name = names[0]
        cfg = STORES[name]
        root = pathlib.Path(args.blob_root or cfg["blob_root"])
        man = pathlib.Path(args.manifest or cfg["manifest"])
        prefix = pathlib.Path(args.snapshot_to)
        prefix.parent.mkdir(parents=True, exist_ok=True)
        blobs = sorted(p.name for p in root.glob(cfg["glob"])) if root.exists() else []
        prefix.with_suffix(".blobs").write_text("\n".join(blobs) + "\n")
        prefix.with_suffix(".manifest").write_text(
            man.read_text() if man.exists() else "")
        print(f"snapshot {name}: {len(blobs)} blob(s), "
              f"{len(_lines(man))} manifest row(s) -> "
              f"{prefix.with_suffix('.blobs')}, "
              f"{prefix.with_suffix('.manifest')}")
        return 0

    bad = False
    print("RET-001 retention check  (stores: " + ", ".join(names) + ")")
    for name in names:
        cfg = STORES[name]
        root = pathlib.Path(args.blob_root or cfg["blob_root"])
        man = pathlib.Path(args.manifest or cfg["manifest"])
        marker = f"/{root.name}/"
        after_blobs = ({p.name for p in root.glob(cfg["glob"])}
                       if root.exists() else set())
        after_rows = _lines(man)
        before_blobs = {pathlib.Path(x).name for x in
                        _lines(pathlib.Path(args.before_blobs)
                               if args.before_blobs else None)}
        before_rows = _lines(pathlib.Path(args.before_manifest)
                             if args.before_manifest else None)
        have_before = bool(args.before_blobs or args.before_manifest)

        print(f"\n  [{name}]  root {root.relative_to(_REPO)}  "
              f"manifest {man.relative_to(_REPO)}")
        print(f"    blobs   before {len(before_blobs):>5}  "
              f"after {len(after_blobs):>5}")
        print(f"    rows    before {len(before_rows):>5}  "
              f"after {len(after_rows):>5}")
        if not have_before:
            # WITHOUT A BEFORE-STATE THE DELTA CHECKS ARE VACUOUS AND MUST SAY
            # SO. An empty `before` makes "nothing was deleted" trivially true
            # and "no new orphan" compare the whole store against itself. The
            # old tool printed `before 0 after 2` and let the checks read as
            # PASS anyway.
            print("    NOTE: no before-state supplied. The delta checks below "
                  "compare against an EMPTY prior store, so R4/R5/R9/R10 are "
                  "vacuous here and their PASS means only 'not measured'. Use "
                  "--snapshot-to before the run to make them real.")

        for code, label, out in _store_checks(name, before_blobs, after_blobs,
                                              before_rows, after_rows, marker):
            gated = (args.gate == "all" or code in _DELTA_CODES)
            vacuous = (not have_before and code in _DELTA_CODES)
            mark = out.state.value
            suffix = ""
            if vacuous:
                suffix = "   [VACUOUS: no before-state]"
            elif not gated:
                suffix = "   [reported, not gating]"
            print(f"    {mark:<15}{code:<6}{label:<44}{out.code}{suffix}")
            if out.state in (State.FAIL, State.BLOCKED):
                print(f"        {out.detail}")
                if gated and not vacuous:
                    bad = True
    print("\n  RET-001 " + ("VIOLATED" if bad else "holds")
          + f"  (gate={args.gate})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
