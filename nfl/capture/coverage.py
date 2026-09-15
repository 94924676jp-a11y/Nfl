"""Per-game T-90 coverage, computed from the plan and the manifest.

WHY THIS MODULE EXISTS: TWO MODULES DISAGREED AND THE WEAKER ONE WAS PRINTING

Measured 2026-09-07, before this module was written:

    registry.unmet_targets(manifest) -> {'unmet': [], 'met': ['final_status',
                                         'inactives', 'practice'], ...}

All three perishable targets reported MET. At that moment no game had reached
its T-90 window -- the first is 2026-09-09T22:50Z, two days out -- and no
capture had ever been attributed to a game. `unmet_targets` answers "has a
source authorised for this kind ever been captured at all", which has no time
dimension and no game dimension. Read as coverage it says a Sunday poll of the
inactives page discharges a Thursday kickoff's T-90 obligation.

`schedule._clears` already refuses exactly that: for a GAME_SPECIFIC_KIND it
requires the capture to carry the target's own game_id, and the capture tool
records no game_id, so under `schedule` no inactives target is clearable. Two
modules, opposite answers to the same question, and the runner printed the
optimistic one. This module makes the game-anchored answer the one that gets
printed, and states plainly what the source-level answer does and does not mean.

WHAT "COVERED" MEANS HERE AND WHAT IT DOES NOT

Covered: a manifest PASS from a source authorised for that kind, whose
`retrieved_at` lies inside THIS target's own window, and which the execution
DECLARED as this exact `(game_id, kind)` obligation before it fetched anything,
under an authorised discharging basis. Nothing weaker counts, and in particular:

  * a capture in the right window from an unauthorised source does not count;
  * a capture from the right source outside the window does not count;
  * a capture of the right kind for another game does not count;
  * a capture declared for another obligation of the SAME game does not count;
  * an unattributed capture does not count, whatever its kind;
  * a run of the periodic cron does not count for anything by itself. Being
    awake is not an observation.

THE 2026-09-07 REGRESSION, AND WHY THE RULE IS NOW UNIVERSAL

This module used to emit one UNATTRIBUTED entry per PASS row --
`(ts, source, None)` -- on the reasoning that a weekly team report legitimately
serves every game that team plays, and `_clears` accepted it for any kind
outside `GAME_SPECIFIC_KINDS`. `practice` is outside it.

Measured on 2026-09-07T21:18Z, with the first T-90 window still 49.5 hours
away: two practice obligations, 2026_01_NE_SEA/practice_a and
2026_01_SF_LA/practice_mon, were reported COVERED and the whole week flipped
DEFERRED -> PASS. What discharged them was the `*/30` periodic vintage sweep at
20:05:40Z and 20:37:36Z -- no declaration, `PERIODIC_SWEEP` basis, `game_id`
None -- and the very same summary said `attributed_captures: 0`. Four
repository assertions caught it; `registry.unmet_targets` had said the same
optimistic thing a week earlier for a different reason.

The reasoning was wrong in the same way twice. Artifact scope -- what the bytes
cover -- is not discharge authority. The governing rule is:

    every event-anchored coverage obligation requires an explicitly declared
    target identity and an authorised discharging execution basis.

So a capture is now dischargeable only through `execution.eligible_targets`,
which exists only where the run declared the target before fetching. The
unattributed captures are still read, still counted, and still in the manifest;
they are classified as ineligible to discharge rather than deleted.
`nfl/tests/fixtures/regression_2026_09_07_practice_false_cover.json` records
the observed bad state and `test_coverage` replays it.

A window that has not closed yet is DEFERRED, never MISSED. Conflating "not yet"
with "failed" is the Class B failure and it would make every plan look broken
the moment it was written.
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import io
import json
import pathlib
import sys
from typing import Optional

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402
from nfl.capture.execution import eligible_targets  # noqa: E402
from nfl.capture.schedule import (GAME_SPECIFIC_KINDS,  # noqa: E402
                                  NON_OBLIGATION_KINDS, CaptureDue,
                                  season_plan)

# EVERY PASS ROW LANDS IN EXACTLY ONE OF THESE, AND AN UNRECOGNISED ROW REFUSES.
#
# WS13 W5, measured 2026-09-14. The manifest has two writers. `capture_vintage`
# writes rows carrying `execution_target` and `discharge_eligibility`;
# `nfl/production/nonqb/inactives.py` writes 18 rows carrying
# `spec_version: "official-inactives-1"`, a `game_id`, a `source_url`, a
# `published_at` and a `sha256` that verifies against the blob on disk -- and
# none of the declaration blocks. Those 18 rows are real, hash-verified,
# game-anchored and chronologically valid, and `eligible_targets` correctly
# returns nothing for them, because Directive 7 section 6 requires the target to
# have been DECLARED before the fetch and they declare nothing.
#
# The defect was never the refusal. It was that the refusal was SILENT: those
# rows fell into an `unattributed` bucket alongside 1,031 periodic sweeps, and
# the coverage report for twelve Sunday games said MISSED with no indication
# that verified evidence for those games was sitting in the same file. A reader
# could not tell "we never fetched it" from "we fetched it and cannot credit
# it", and those need opposite responses -- one is a capture failure, the other
# is a schema and declaration failure.
#
# So each row is now classified by name, the classes are counted, and a row that
# matches none of them BLOCKS the report instead of being absorbed.
#
# THIS CHANGES NO VERDICT. Covered stays covered, missed stays missed. Nothing
# here credits an undeclared row with a discharge and nothing here rewrites a
# manifest row. The 47 missed week-1 targets are still 47 missed targets.
DISPOSITIONS = (
    "DISCHARGING",             # declared, eligible, verified -- may discharge
    "DECLARED_NOT_ELIGIBLE",   # declared a target, bytes refused it, reasons
    "SWEEP_NO_OPEN_TARGET",    # declared, no target open at declaration time
    "LEGACY_PRE_DIRECTIVE_7",  # post-hoc `discharge_claims` only
    "FOREIGN_SCHEMA",          # a second writer, under a declared spec_version
    "PRE_DECLARATION_CAPTURE", # a capture row written before declarations
    "UNDECLARED_NO_ARTIFACT",  # no declaration and no blob reference either
    "ARTIFACT_UNVERIFIED",     # blob absent, unreadable, or hash mismatch
)

# EVERY `spec_version` THIS MODULE KNOWS HOW TO READ. A row carrying one that is
# not here BLOCKS the report.
#
# This is the prospective half of the W5 repair. A second writer announces
# itself in exactly one place -- it stamps its own `spec_version` -- so that is
# where the check belongs. `nfl/production/nonqb/inactives.py` appended 18 rows
# under `official-inactives-1` and nothing anywhere noticed; the rows simply
# stopped counting. The next writer will be refused by name instead.
#
#   None                        `nfl/tools/capture_vintage.py`, the capture tool
#   official-inactives-1        `nfl/production/nonqb/inactives.py`, WS13 4a
#   delivered_injuries/1.0.0    `nfl/tools/ingest_delivered_injuries.py`
KNOWN_SPEC_VERSIONS = (None, "official-inactives-1", "delivered_injuries/1.0.0")

# Measured 2026-09-14 on nfl/vintage_manifest.jsonl, 1,061 PASS rows:
#   DISCHARGING 12 - DECLARED_NOT_ELIGIBLE and SWEEP_NO_OPEN_TARGET 963 -
#   LEGACY_PRE_DIRECTIVE_7 6 - FOREIGN_SCHEMA 18 - PRE_DECLARATION_CAPTURE 62 -
#   ARTIFACT_UNVERIFIED 0 excluded rows re-classified under their own class.
# The counts are reported by `performed_from_manifest`; they are recomputed on
# every call and nothing here hard-codes them.


def _parse_ts(v) -> Optional[dt.datetime]:
    if not v:
        return None
    try:
        d = dt.datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def _blob_ok(value: dict) -> tuple:
    """Does the raw artifact exist, and does a digest OF THE STORED BYTES match?

    Directive 7 §5 requires "a real persisted raw artifact" for discharge, and
    §9.9/§9.11 require that a persistence failure or a wrong hash PREVENTS
    coverage. A manifest row is a claim about a file; this opens the file.

    WS-K'S PATCH, TAKEN AS WRITTEN (WS_K_PERSISTED_PROVENANCE.md §10).

    The `sha256` on a `durability: "reduce"` row is the digest of the UPSTREAM
    file, and the file actually persisted is a column-reduced subset whose own
    hash was never recorded. Checking the stored bytes against `sha256` is
    therefore guaranteed to mismatch, which is how all 368 reduce rows read as
    RAW_SHA256_MISMATCH -- a number that sounds like corruption and is not.
    WS-K recovered a persisted digest for 216 of them and established that the
    other 152 have no attested digest of their stored bytes and never will.

    THE TRAP, AND IT IS LOAD-BEARING. A reduce row with no persisted digest must
    NOT fall back to `value["sha256"]`. That field describes bytes that were
    never stored; using it re-asserts, silently, the exact claim WS-K disproved.
    Those 152 rows get their own code and read as CANNOT BE CHECKED -- never as
    wrong, never as fine. Hashing an unattested blob and recording the result
    would be circular and is refused.

    NO COVERAGE VERDICT MOVES ON THIS. All 368 reduce rows carry
    `discharge_eligibility.n_eligible == 0`: they discharge nothing and never
    could. The 47 missed week-1 windows stay missed.
    """
    import hashlib as _hashlib
    from nfl.capture.persisted_provenance import (load_recovery, read_blob,
                                                  resolve_blob)
    blob = (value or {}).get("blob")
    if not blob:
        return False, "RAW_ARTIFACT_NOT_PERSISTED"

    # Prefer a digest that covers the bytes ACTUALLY PERSISTED.
    sha = (value or {}).get("persisted_content_sha256")
    if not sha:
        rec = _recovery().get(blob)
        if rec and rec.get("persisted_content_sha256"):
            sha = rec["persisted_content_sha256"]

    if not sha:
        if (value or {}).get("durability") == "reduce":
            return False, "PERSISTED_DIGEST_ABSENT_HISTORICAL"
        sha = (value or {}).get("sha256")

    if not sha or len(sha) != 64:
        return False, "RAW_SHA256_ABSENT_OR_MALFORMED"

    # Also resolves the rows that cite `...reduced.csv` when only
    # `...reduced.csv.gz` exists (WS13 §3c).
    path, _how = resolve_blob(blob)
    if path is None:
        return False, f"RAW_ARTIFACT_MISSING_ON_DISK:{blob}"
    try:
        raw = read_blob(path)
    except OSError as exc:
        return False, f"RAW_ARTIFACT_UNREADABLE:{type(exc).__name__}"
    if _hashlib.sha256(raw).hexdigest() != sha:
        return False, "PERSISTED_CONTENT_SHA256_MISMATCH"
    return True, None


_RECOVERY_CACHE = {}


def _recovery() -> dict:
    """The persisted-digest sidecar, read once per process.

    `performed_from_manifest` calls `_blob_ok` 1,061 times; re-reading the
    sidecar on each would turn one file read into a thousand. Cached by
    identity of the file's mtime and size so a rebuilt sidecar is picked up
    rather than a stale dict being served forever.
    """
    from nfl.capture.persisted_provenance import RECOVERY, load_recovery
    p = pathlib.Path(RECOVERY)
    key = (str(p), p.stat().st_mtime_ns, p.stat().st_size) if p.exists() else None
    if key not in _RECOVERY_CACHE:
        _RECOVERY_CACHE.clear()
        _RECOVERY_CACHE[key] = load_recovery()
    return _RECOVERY_CACHE[key]


def _disposition(val: dict, artifact_ok: bool, n_eligible: int) -> str:
    """Which named class this PASS row belongs to. Never a default.

    Order matters and is deliberate: artifact verification comes first because a
    row whose bytes do not verify is not evidence of anything regardless of what
    it declared, and reporting it under its declaration would credit a claim the
    file cannot support.
    """
    if not artifact_ok:
        return "ARTIFACT_UNVERIFIED"
    if n_eligible:
        return "DISCHARGING"
    decl = val.get("execution_target") or {}
    if val.get("discharge_eligibility") is not None:
        block = val.get("discharge_eligibility") or {}
        return ("DECLARED_NOT_ELIGIBLE" if block.get("targets")
                else "SWEEP_NO_OPEN_TARGET")
    if decl:
        return "SWEEP_NO_OPEN_TARGET"
    if val.get("discharge_claims"):
        return "LEGACY_PRE_DIRECTIVE_7"
    if val.get("spec_version"):
        return "FOREIGN_SCHEMA"
    # WRITTEN BEFORE DIRECTIVE 7 EXISTED, not written wrongly. 68 rows from
    # 2026-09-06/07 carry a blob, a clock and a hash and no declaration block of
    # any kind, because the mechanism that writes one was added on 2026-09-07.
    # They discharge nothing -- there is no intent to read -- and they are named
    # rather than lumped in with the sweeps, because "declared and the bytes
    # were refused" and "predates declaration entirely" are different facts.
    return ("PRE_DECLARATION_CAPTURE" if val.get("blob")
            else "UNDECLARED_NO_ARTIFACT")


def _uncredited(val: dict, source: str, ts, capture_id) -> Optional[dict]:
    """A verified, game-anchored capture that is not permitted to discharge.

    Returned for REPORTING only. It never reaches `_clears` and never changes a
    target's state. What it answers is the question a MISSED line cannot: did we
    hold bytes for this game, from an authorised source, before kickoff, that we
    are refusing to credit -- and if so, on what ground.
    """
    gid = val.get("game_id")
    if not gid or not ts:
        return None
    return {"game_id": gid, "source": source, "capture_id": capture_id,
            "retrieved_at": ts.isoformat(),
            "spec_version": val.get("spec_version"),
            "source_url": val.get("source_url"),
            "published_at": val.get("published_at"),
            "sha256": val.get("sha256"),
            "refusal": ("NO_DECLARATION_BLOCK"
                        if val.get("discharge_eligibility") is None
                        else "DECLARED_BUT_REFUSED")}


def performed_from_manifest(manifest_path, *, verify_artifacts: bool = True
                            ) -> Outcome:
    """Every capture that may discharge something, as `(retrieved_at, source,
    game_id)`, with the reasons anything was excluded.

    THE MANIFEST HAS TWO SCHEMAS AND THE FIRST VERSION OF THIS READ ONE

    Measured 2026-09-07 on the live manifest: 54 of 60 PASS rows nest the real
    clock under `value.provenance.retrieved_at`, and 6 older rows carry it at
    `value.retrieved_at`. This function originally read only the top level, so
    it silently dropped 54 rows -- 90% of the evidence -- and reported
    `total_captures: 6`. Both locations are read now, and a PASS row carrying
    NEITHER is a refusal rather than a skip.

    WHAT COUNTS AS ATTRIBUTED CHANGED UNDER DIRECTIVE 7

    Only `discharge_eligibility` entries marked eligible are emitted as
    attributed captures, and those exist only where the run DECLARED the target
    before fetching. The older `discharge_claims` field is read for reporting
    but discharges nothing: it inferred its target set from `retrieved_at` after
    the fact, which §6 forbids. Those rows stay in the manifest as history.
    """
    mp = pathlib.Path(manifest_path)
    if not mp.exists():
        return Outcome.not_applicable(
            "NO_MANIFEST", f"no manifest at {mp}; nothing has been captured "
                           f"through this record, so there are no performed "
                           f"captures to judge coverage against.")
    out, undated, n_pass, excluded = [], [], 0, []
    legacy = 0
    unattributed = 0
    disposition_counts = {d: 0 for d in DISPOSITIONS}
    unclassified = []
    uncredited = []
    # ROWS AND TARGET-PAIRS ARE DIFFERENT UNITS AND THE COUNTERS CONFLATED THEM.
    #
    # `out` holds one entry per (game_id, kind) a row DECLARED, so a single
    # league-wide capture that names eight targets contributes eight entries.
    # `unattributed` counts ROWS. Adding the two and comparing to the row count
    # therefore could not balance once any row declared more than one target:
    # measured 2026-09-11, 103 emitted pairs came from just 12 rows, and
    # 103 + 958 = 1061 against 970 PASS rows. The identity that actually holds
    # is over rows, so the row count is now tracked separately and reported.
    attributed_rows = 0
    for line in mp.read_text().splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("state") != "PASS":
            continue
        n_pass += 1
        val = row.get("value") or {}
        prov = val.get("provenance") or {}
        ts = _parse_ts(val.get("retrieved_at") or prov.get("retrieved_at"))
        if ts is None:
            undated.append(row.get("source"))
            continue
        if val.get("discharge_claims") and not val.get("discharge_eligibility"):
            legacy += 1

        ok, why = ((True, None) if not verify_artifacts
                   else _blob_ok(val))
        targets = eligible_targets(val) if ok else []
        disp = _disposition(val, ok, len(targets))
        disposition_counts[disp] += 1
        if val.get("spec_version") not in KNOWN_SPEC_VERSIONS:
            # NEVER A SILENT DEFAULT. An unknown `spec_version` means a writer
            # this module has never read has appended to the manifest, and the
            # honest answer is that this week's coverage is unknown until the
            # schema is named -- not that those rows contribute nothing. That
            # silence is what hid 18 verified game-anchored inactives rows.
            unclassified.append({"source": row.get("source"),
                                 "capture_id": row.get("capture_id"),
                                 "spec_version": val.get("spec_version"),
                                 "keys": sorted(val.keys())[:12]})
        if disp in ("FOREIGN_SCHEMA", "DECLARED_NOT_ELIGIBLE",
                    "PRE_DECLARATION_CAPTURE"):
            u = _uncredited(val, row.get("source"), ts, row.get("capture_id"))
            if u:
                uncredited.append(u)
        if not ok:
            excluded.append({"source": row.get("source"),
                             "capture_id": row.get("capture_id"),
                             "reason": why})
            unattributed += 1
            continue
        if not targets:
            # Real evidence, kept in the manifest, discharging nothing. This
            # line used to append `(ts, source, None)` and that unattributed
            # entry is what discharged two practice obligations on 2026-09-07.
            unattributed += 1
            continue
        attributed_rows += 1
        for gid, kind in targets:
            out.append((ts, row.get("source"), gid, kind))

    if unclassified:
        seen = sorted({str(u.get("spec_version")) for u in unclassified})
        return Outcome.blocked(
            "MANIFEST_SPEC_VERSION_UNKNOWN",
            f"{len(unclassified)} of {n_pass} PASS rows carry a spec_version "
            f"this module has never read: {seen}. Known: "
            f"{list(KNOWN_SPEC_VERSIONS)}. A second writer appending under an "
            f"unread schema is exactly how 18 verified, game-anchored, "
            f"pre-kickoff inactives rows became invisible to this report for "
            f"twelve games. Read the schema and add it here; do not let the "
            f"rows count as nothing by default.",
            cause=Cause.DATA, unclassified=unclassified[:20],
            n_unclassified=len(unclassified), n_pass=n_pass,
            unknown_spec_versions=seen)
    if undated:
        return Outcome.blocked(
            "CAPTURE_CLOCK_UNREADABLE",
            f"{len(undated)} of {n_pass} PASS rows carry no readable "
            f"retrieved_at at value.retrieved_at or value.provenance."
            f"retrieved_at: {sorted(set(undated))}. An undated capture cannot "
            f"be placed inside or outside a window, and skipping it would "
            f"understate coverage silently.",
            cause=Cause.DATA, undated_sources=sorted(set(undated)),
            n_undated=len(undated), n_pass=n_pass)
    return Outcome.ok("CAPTURES_READ", value=out,
                      detail=f"{len(out)} dischargeable captures of {n_pass} "
                             f"dated PASS rows; {unattributed} carry no "
                             f"declared eligible target and discharge nothing; "
                             f"{len(excluded)} excluded on artifact "
                             f"verification; {legacy} legacy pre-Directive-7 "
                             f"rows discharge nothing",
                      n_captures=len(out), n_pass_rows=n_pass,
                      n_attributed_rows=attributed_rows,
                      n_unattributed=unattributed,
                      row_identity_balances=(attributed_rows + unattributed
                                             == n_pass),
                      units_note=('n_captures counts (game_id, kind) target '
                                  'pairs; n_attributed_rows and '
                                  'n_unattributed count manifest ROWS. Only '
                                  'the row counts partition n_pass_rows.'),
                      artifact_excluded=excluded, legacy_claim_rows=legacy,
                      disposition_counts=disposition_counts,
                      dispositions_partition_pass_rows=(
                          sum(disposition_counts.values()) == n_pass),
                      uncredited_game_anchored=uncredited,
                      n_uncredited_game_anchored=len(uncredited))


def _schedule_snapshots(vintage_dir: pathlib.Path, manifest_path=None,
                        as_of=None):
    """Schedule blobs ordered by WHEN WE LEARNED THEM, oldest first.

    P7, 2026-09-15. This used `key=lambda p: p.stat().st_mtime`, which is the
    first entry on `vintage_selector`'s forbidden list -- "filesystem mtime as
    information time" -- and it is forbidden for two separate reasons that both
    bite here. A checkout, a copy or a `touch` reorders it, so the plan is not
    reproducible; and mtime is not a clock on the bytes, so a blob that the
    manifest cannot date at all still sorts somewhere.

    MEASURED on this tree the same day: 134 `schedules.*.csv.gz` blobs are on
    disk and 48 of them appear in NO manifest row. Under the old ordering one
    of those orphans could be, and for the sibling reader
    `team_volume_v1.coaches` (which takes `sorted(glob)[-1]`) actually IS, the
    file a production input is read from -- with no retrieval instant, no
    provenance and no content attribution.

    So the order now comes from `bitemporal`, over the manifest, on transaction
    time. Orphans are RETURNED LAST and COUNTED rather than dropped: dropping
    them would hide the retention defect, and this module is not the place to
    fix it. The fallback to mtime survives for the case where no manifest row
    matches anything on disk -- a caller passing a synthetic `vintage_dir` --
    and the basis is reported so a reader can tell the two apart.
    """
    blobs = sorted(vintage_dir.glob("schedules.*.csv.gz"))
    if not blobs:
        return [], {"basis": "NONE", "n_blobs": 0, "n_orphan": 0}
    learned = {}
    try:
        from nfl.capture import bitemporal as _BT
        for f in _BT.facts_from_manifest(manifest_path=manifest_path,
                                         source="schedules"):
            if f.blob:
                learned[pathlib.Path(f.blob).name] = f.learned_at
    except Exception:                                        # noqa: BLE001
        # NAMED, NOT SWALLOWED: the basis below records that the manifest was
        # unreadable, so a degraded ordering cannot pass for the good one.
        learned = {}
    clocked = [(learned[b.name], b) for b in blobs if learned.get(b.name)]
    orphans = [b for b in blobs if not learned.get(b.name)]
    if as_of is not None:
        from nfl.capture import bitemporal as _BT2
        cut = _BT2.parse(as_of)
        clocked = [(t, b) for t, b in clocked if _BT2.parse(t) < cut]
        orphans = []      # an undateable blob is never lawful under a cut
    if not clocked:
        return (sorted(blobs, key=lambda p: p.stat().st_mtime),
                {"basis": "FILESYSTEM_MTIME_FALLBACK", "n_blobs": len(blobs),
                 "n_orphan": len(orphans),
                 "note": ("no schedules blob on disk could be dated from the "
                          "manifest, so the order is mtime and is NOT "
                          "information time. Reported, not hidden.")})
    clocked.sort(key=lambda tb: (tb[0], tb[1].name))
    return ([b for _t, b in clocked] if as_of is not None
            else orphans + [b for _t, b in clocked]), {
        "basis": "MANIFEST_RETRIEVED_AT", "n_blobs": len(blobs),
        "n_clocked": len(clocked), "n_orphan": len(orphans),
        "newest_learned_at": clocked[-1][0],
        "note": ("ordered on transaction time; blobs with no manifest row are "
                 "ordered FIRST so they can never win, and counted so the "
                 "retention gap stays visible")}


def load_week_plan(season: int, week: int, vintage_dir=None,
                   manifest_path=None, as_of=None) -> Outcome:
    """The capture plan for one week, built from the captured schedule snapshot.

    The schedule is itself a captured artifact rather than a constant, so the
    plan inherits its vintage. If no snapshot has been captured there is no plan
    and this refuses; inventing kickoff times to keep a report populated is the
    exact defect class this project exists to prevent.

    `as_of` is OPTIONAL and defaults to no bound, which is correct for this
    reader and is worth saying why: the plan reads `season`, `week`,
    `game_type`, `gameday`, `gametime` and the team codes, and a kickoff TIME
    is scheduled months ahead. None of those columns is a realised outcome. The
    same blob DOES carry `result`, `home_score`, `spread_line` and
    `total_line` -- measured on `schedules.bfb4ca5952e3a974.csv.gz`, week-1
    results present for 15 of 16 games and `total_line` for weeks 1 and 2 --
    and this function reads none of them. The guard against that leak is the
    absence of a reader, which is a weaker guarantee than a bound, so `as_of`
    exists for a caller who wants the bound as well.
    """
    vintage_dir = pathlib.Path(vintage_dir or (_REPO / "nfl" / "vintage"))
    snaps, order = _schedule_snapshots(vintage_dir, manifest_path=manifest_path,
                                       as_of=as_of)
    if not snaps:
        return Outcome.blocked(
            "NO_SCHEDULE_SNAPSHOT",
            "no schedules artifact has been captured, so no kickoff time is "
            "known and no T-90 target can be located in time. There is no "
            "plan to check coverage against.",
            cause=Cause.DEPENDENCY, searched=str(vintage_dir),
            snapshot_order=order)
    latest = snaps[-1]
    rows = [r for r in csv.DictReader(
                io.StringIO(gzip.open(latest, "rt").read()))
            if r.get("season") == str(season)
            and r.get("game_type") == "REG"
            and r.get("week") == str(week)]
    if not rows:
        return Outcome.blocked(
            "NO_GAMES_IN_SNAPSHOT",
            f"the schedule snapshot {latest.name} carries no {season} regular "
            f"season week {week} rows. An empty plan is not full coverage.",
            cause=Cause.DATA, snapshot=latest.name, snapshot_order=order)
    plan = season_plan(rows)
    return Outcome.ok(
        "WEEK_PLAN_BUILT", value=plan,
        detail=f"{len(plan)} targets across {len(rows)} games, from "
               f"{latest.name}",
        snapshot=latest.name, n_games=len(rows), n_targets=len(plan),
        snapshot_order=order)


def coverage(season: int, week: int, *, manifest_path,
             now: Optional[dt.datetime] = None, vintage_dir=None,
             verify_artifacts: bool = True) -> Outcome:
    """Per-target coverage for one week. The game-anchored answer."""
    now = now or dt.datetime.now(dt.timezone.utc)
    planned = load_week_plan(season, week, vintage_dir=vintage_dir)
    from sportsplatform.governance.outcome import State
    if planned.state is not State.PASS:
        return planned
    plan = planned.value
    read = performed_from_manifest(manifest_path,
                                   verify_artifacts=verify_artifacts)
    if read.state is State.BLOCKED:
        return read
    performed = read.value if read.state is State.PASS else []

    from nfl.capture.schedule import _clears
    covered, missed, pending = [], [], []
    for c in plan:
        if c.kind in NON_OBLIGATION_KINDS:
            continue
        lo, hi = c.window
        hit = [p for p in performed if _clears(c, p)]
        if hit:
            covered.append((c, min(h[0] for h in hit)))
        elif hi <= now:
            missed.append(c)
        else:
            pending.append(c)

    # WHY A MISSED TARGET NOW CARRIES A SECOND LINE, AND WHY IT STILL SAYS
    # MISSED.
    #
    # WS13 section 4a: twelve of the 47 week-1 misses are games for which the
    # store DOES hold hash-verified, game-anchored, pre-kickoff inactives bytes
    # -- written by a second manifest writer, under a schema carrying no
    # declaration block, therefore not dischargeable and correctly refused. The
    # report said MISSED and stopped there, and a reader could not tell that
    # case apart from a game we never fetched anything for. They need opposite
    # responses.
    #
    # THIS IS NOT A BACKFILL AND IT DOES NOT MOVE A SINGLE TARGET. `missed`
    # above is computed before this block and is not touched by it. Nothing
    # below feeds `_clears`, nothing rewrites a manifest row, and no target
    # changes state. The 47 are still 47. What changes is that the report now
    # distinguishes a capture failure from a declaration-and-schema failure, and
    # names which of the two each miss is.
    from nfl.capture.registry import can_discharge
    uncredited = read.evidence.get("uncredited_game_anchored", []) or []
    with_evidence, dark = [], []
    for c in missed:
        lo, hi = c.window
        hits = [u for u in uncredited
                if u["game_id"] == c.game_id
                and can_discharge(u["source"], c.kind)
                and (_parse_ts(u["retrieved_at"]) is not None)
                and lo <= _parse_ts(u["retrieved_at"]) <= hi]
        if hits:
            with_evidence.append({
                "game_id": c.game_id, "kind": c.kind,
                "still_missed": True,
                "why_not_discharged": sorted({h["refusal"] for h in hits}),
                "uncredited_rows": hits})
        else:
            dark.append({"game_id": c.game_id, "kind": c.kind})

    summary = {
        "season": season, "week": week,
        "as_of_utc": now.isoformat(),
        "n_targets": len(covered) + len(missed) + len(pending),
        "covered": len(covered), "missed": len(missed),
        "not_yet_due": len(pending),
        "game_specific_kinds": list(GAME_SPECIFIC_KINDS),
        # UNITS, NAMED IN THE KEY FROM NOW ON.
        #
        # `attributed_captures` counts (game_id, kind) PAIRS and always has.
        # Its name reads as rows, and because every emitted pair carries a
        # game_id it is identically equal to `dischargeable_captures`: two
        # names, one number, and neither of them the row count a reader
        # reaches for. Measured 2026-09-14 it is 103 against 12 rows.
        #
        # IT IS NOT REDEFINED HERE. Three test modules and
        # `capture_vintage.py` read this key, and silently changing what a
        # published number means is worse than an awkward name. The row unit
        # is added beside it under a key that says which unit it is.
        "attributed_rows": read.evidence.get("n_attributed_rows", 0),
        "dischargeable_target_pairs": len(performed),
        "attributed_captures": sum(1 for p in performed if p[2]),
        "dischargeable_captures": len(performed),
        "unattributed_captures": read.evidence.get("n_unattributed", 0),
        "total_pass_rows": read.evidence.get("n_pass_rows", 0),
        "total_captures": len(performed),
        "row_dispositions": read.evidence.get("disposition_counts", {}),
        "dispositions_partition_pass_rows": read.evidence.get(
            "dispositions_partition_pass_rows"),
        # The W5 split of the misses. Both lists are still MISSED.
        "missed_with_uncredited_evidence": len(with_evidence),
        "missed_with_no_evidence_at_all": len(dark),
        "uncredited_detail": with_evidence,
        "artifacts_verified": verify_artifacts,
        "artifact_excluded": read.evidence.get("artifact_excluded", []),
        "legacy_claim_rows": read.evidence.get("legacy_claim_rows", 0),
        "missed_detail": [c.as_dict() for c in missed],
        "next_window": min((c.as_dict() for c in pending),
                           key=lambda d: d["window_start_utc"], default=None),
    }

    if missed:
        return Outcome.fail(
            "PERISHABLE_WINDOWS_MISSED",
            f"{len(missed)} of {summary['n_targets']} targets had their window "
            f"close with no authorised, in-window, game-attributed capture. "
            f"These are not recoverable later: the pages they name are "
            f"overwritten in place. Of them, {len(with_evidence)} have "
            f"hash-verified game-anchored bytes in this same manifest that no "
            f"rule permits to discharge them, and {len(dark)} have nothing at "
            f"all. Both are misses; they are different defects.",
            **summary)
    if not covered:
        return Outcome.deferred(
            "NO_WINDOW_HAS_CLOSED_YET",
            f"{len(pending)} targets are planned and none has come due. "
            f"Nothing is covered and nothing is missed. This is the honest "
            f"state before a season opens, and it must not be read as "
            f"coverage -- registry.unmet_targets reports these kinds as met on "
            f"the strength of out-of-window polls, which is a source-level "
            f"answer to a game-level question.",
            owed=[c.as_dict() for c in pending][:5], **summary)
    return Outcome.ok(
        "WINDOWS_COVERED", value=summary,
        detail=f"{len(covered)} covered, {len(pending)} not yet due, none "
               f"missed", **summary)


def event_anchored(plan: list, cadence_minutes: int) -> Outcome:
    """Can a fixed periodic cron discharge these targets? Answer with evidence.

    This is the question the workflow comment answered by arithmetic: an 80
    minute window against a 30 minute cadence "lands at least twice inside it".
    Two things are wrong with reading that as fulfilment.

    First, coverage in TIME is not attribution to a GAME. A run that happens to
    be inside game A's window captures a league-wide page and records no
    game_id, so it discharges nothing under `_clears`.

    Second, the arithmetic assumes the cron fires. GitHub documents that
    scheduled runs may be delayed or dropped under load, and a dropped run is
    not a delayed one. The measured base rate here is n=3 scheduled runs, which
    cannot support any statement about drop probability.

    So this returns the timing fact and refuses to convert it into a discharge
    claim.
    """
    # EVERY obligation-bearing kind needs anchoring, not only the per-game
    # artifact kinds. Restricting this to GAME_SPECIFIC_KINDS understated the
    # requirement by exactly the set -- practice, final_status -- that the
    # 2026-09-07 false cover was discharged in.
    windows = [c for c in plan if c.kind not in NON_OBLIGATION_KINDS]
    if not windows:
        return Outcome.not_applicable(
            "NO_ANCHORED_TARGETS",
            "this plan carries no coverage obligations, so no event anchoring "
            "is required for it.")
    widths = {int((c.window[1] - c.window[0]).total_seconds() // 60)
              for c in windows}
    narrowest = min(widths)
    return Outcome.blocked(
        "PERIODIC_CADENCE_IS_NOT_EVENT_ANCHORING",
        f"{len(windows)} per-game targets, narrowest window {narrowest} "
        f"minutes, against a {cadence_minutes}-minute periodic cadence. A "
        f"periodic run can only ever make a capture LIKELY to fall inside a "
        f"window; it cannot make that capture attributable to the game whose "
        f"window it fell in, and `schedule._clears` correctly refuses an "
        f"unattributed capture for a game-specific kind. Closing this needs an "
        f"execution anchored on `next_target`, and a capture row carrying the "
        f"game_id it was taken for.",
        cause=Cause.DEPENDENCY,
        n_windows=len(windows), narrowest_window_minutes=narrowest,
        cadence_minutes=cadence_minutes,
        distinct_window_widths=sorted(widths))
