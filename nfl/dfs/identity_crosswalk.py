"""DK Showdown salary-pool identity crosswalk.

Resolves each distinct (player, team) row of a DK Showdown slice to a
canonical ``gsis_id`` from a frozen game-truth snapshot.

Governing constraints, all owner-stated:

* The DK file is a **salary and player-universe candidate**, never a source
  of projections and never a source of identity. Identity flows one way:
  DK name -> canonical roster. A DK row that does not resolve stays
  unresolved and is surfaced.
* Matching is **exact within team** after a declared normalisation. No
  fuzzy matching, no edit distance, no "closest" fallback. An ambiguous or
  absent match is reported, never guessed.
* Team DST rows sit on **their own identity axis**. A DST is not a player
  and has no ``gsis_id``; resolving it against the player roster would be a
  category error, so it is classified rather than matched.

The normalisation is deliberately narrow and is declared in the artifact so
a reader can reproduce it: strip accents, drop ``.'-``, casefold, drop a
trailing generational suffix. It does not touch the interior of a name.
"""
from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

CONTRACT = "dfs-identity-crosswalk/1.0.0"

#: Normalisation steps applied to both sides before comparison, in order.
NORMALISATION = (
    "unicode NFKD, drop non-ascii",
    "remove the characters . ' -",
    "casefold and collapse whitespace",
    "drop a trailing generational suffix (jr sr ii iii iv v)",
)

_PUNCT = re.compile(r"[.'\-]")
_SUFFIX = re.compile(r"\s+(jr|sr|ii|iii|iv|v)$")
_SPACE = re.compile(r"\s+")

# DK encodes the Showdown captain slot as a separate row for the same human.
# It is a pricing construct, not an identity.
_ROSTER_SLOTS = {"CPTN", "CPT", "FLEX"}


def normalise(name: str) -> str:
    """Return the comparison key for ``name``. See :data:`NORMALISATION`."""
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    s = _PUNCT.sub("", s).casefold().strip()
    s = _SPACE.sub(" ", s)
    return _SUFFIX.sub("", s)


class CrosswalkError(RuntimeError):
    """Raised when an input cannot support a crosswalk at all."""


def _index_roster(snapshot: dict) -> tuple[dict[str, dict[str, list[dict]]], int]:
    """Index named roster players by team, then by normalised name.

    Players the truth layer could not name are excluded from the index and
    counted separately: an unnamed roster row cannot participate in a
    name match, and silently dropping it would overstate coverage.
    """
    index: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    unnamed = 0
    for player in snapshot.get("players", ()):
        name = player.get("full_name")
        if not name:
            unnamed += 1
            continue
        index[player["team"]][normalise(name)].append(player)
    if not index:
        raise CrosswalkError("truth snapshot carries no named players")
    return index, unnamed


def _is_dst(positions: set[str]) -> bool:
    """A row is a team defence when DST is its only non-slot position."""
    football = positions - _ROSTER_SLOTS
    return football == {"DST"}


def crosswalk(dk_rows, snapshot: dict) -> dict:
    """Resolve DK rows against ``snapshot``. Returns the artifact body."""
    index, unnamed = _index_roster(snapshot)

    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in dk_rows:
        grouped[(row["Player"], row["Team"])].append(row)
    if not grouped:
        raise CrosswalkError("DK slice carries no rows")

    entries = []
    for (name, team), rows in sorted(grouped.items()):
        positions = {r["Pos"] for r in rows}
        salaries = sorted({int(r["Salary"]) for r in rows if r.get("Salary")})
        entry = {
            "dk_name": name,
            "dk_team": team,
            "dk_positions": sorted(positions),
            "dk_salaries": salaries,
            "dk_row_count": len(rows),
        }
        if _is_dst(positions):
            entry["resolution"] = "TEAM_DST_AXIS"
            entry["gsis_id"] = None
            entry["note"] = "team defence; not a player identity and carries no gsis_id"
            entries.append(entry)
            continue

        key = normalise(name)
        candidates = index.get(team, {}).get(key, [])
        if len(candidates) == 1:
            entry["resolution"] = "EXACT_WITHIN_TEAM"
            entry["gsis_id"] = candidates[0]["gsis_id"]
            entry["roster_name"] = candidates[0]["full_name"]
        elif len(candidates) > 1:
            entry["resolution"] = "AMBIGUOUS_WITHIN_TEAM"
            entry["gsis_id"] = None
            entry["candidates"] = [c["gsis_id"] for c in candidates]
        else:
            entry["resolution"] = "UNRESOLVED_NO_MATCH"
            entry["gsis_id"] = None
        entries.append(entry)

    counts: dict[str, int] = defaultdict(int)
    for e in entries:
        counts[e["resolution"]] += 1

    return {
        "contract": CONTRACT,
        "normalisation": list(NORMALISATION),
        "roster_players_unnamed_excluded": unnamed,
        "dk_distinct_player_team": len(entries),
        "counts": dict(counts),
        "entries": entries,
    }


def assert_complete(artifact: dict) -> None:
    """Raise unless every non-DST DK row resolved to exactly one identity.

    This is the acceptance gate. It exists so a partial crosswalk cannot be
    consumed as though it were complete; a miss must be seen, not averaged
    away. Callers that want the partial result should read the artifact
    directly rather than relaxing this.
    """
    counts = artifact["counts"]
    bad = {
        k: v
        for k, v in counts.items()
        if k in ("AMBIGUOUS_WITHIN_TEAM", "UNRESOLVED_NO_MATCH") and v
    }
    if bad:
        detail = ", ".join(f"{k}={v}" for k, v in sorted(bad.items()))
        raise CrosswalkError(f"crosswalk incomplete: {detail}")


def load_dk_slice(path: Path) -> list[dict]:
    with open(path, newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise CrosswalkError(f"DK slice is empty: {path}")
    missing = {"Player", "Team", "Pos"} - set(rows[0])
    if missing:
        raise CrosswalkError(f"DK slice missing columns {sorted(missing)}: {path}")
    return rows


def build(dk_path: Path, snapshot_path: Path) -> dict:
    snapshot = json.loads(Path(snapshot_path).read_text())
    artifact = crosswalk(load_dk_slice(Path(dk_path)), snapshot)
    artifact["inputs"] = {
        "dk_slice": str(dk_path),
        "truth_snapshot": str(snapshot_path),
        "truth_contract": snapshot.get("contract"),
        "game_id": snapshot.get("game_id"),
    }
    return artifact
