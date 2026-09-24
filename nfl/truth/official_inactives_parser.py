"""Parse official game-day inactive lists out of preserved capture bytes.

This module exists because of a specific defect: the NFL.com ``/inactives/``
landing page returns HTTP 200 and ~400 KB for every capture, and 363 of the
367 preserved blobs are an explicit empty-state page reading *"Please check
back soon for NFL Inactive Reports for this Season."* A capture PASS on that
page means the fetch succeeded, not that an inactive list was obtained. So the
first thing this parser does is refuse that page **by name**.

Two carriers are proven to work, both already present in the capture history:

1. **The NFL.com weekly article**, e.g.
   ``/news/inactive-reports-sunday-week-1-2026-nfl-season``. Server-rendered,
   not a hydration shell, laid out as ``<h3>TEAM</h3><ul><li>POS Name</li>…``
   per game.
2. **An operator relay**, plain text, laid out as a bare team abbreviation
   followed by ``* POS Name`` lines.

What this module will not do
============================
It reports only what the bytes literally contain. It does not infer ACTIVE
from omission -- a player absent from an inactive list is *unlisted*, which is
a different claim from *active*, and callers get the listed set only. It does
not convert an injury designation into an inactive. It does not fuzzy-match
team names. A document it cannot parse raises rather than returning an empty
result, because an empty result read as success is this project's Class A
defect and is the reason this file exists.
"""
from __future__ import annotations

import gzip
import html as _html
import re
from pathlib import Path

CONTRACT = "official-inactives-parser/1.0.0"

#: The literal string the NFL.com landing page shows when it has no report.
EMPTY_STATE_MARKER = "Please check back soon for NFL Inactive Reports"

#: Team abbreviations as the relay and the article use them.
TEAM_ABBRS = {
    "ARI", "AZ", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL",
    "DEN", "DET", "GB", "HOU", "IND", "JAX", "KC", "LA", "LAC", "LAR",
    "LV", "MIA", "MIN", "NE", "NO", "NYG", "NYJ", "PHI", "PIT", "SEA",
    "SF", "TB", "TEN", "WAS",
}

#: Full club nicknames as the article's <h3> headers use them, uppercased.
NICKNAME_TO_ABBR = {
    "CARDINALS": "ARI", "FALCONS": "ATL", "RAVENS": "BAL", "BILLS": "BUF",
    "PANTHERS": "CAR", "BEARS": "CHI", "BENGALS": "CIN", "BROWNS": "CLE",
    "COWBOYS": "DAL", "BRONCOS": "DEN", "LIONS": "DET", "PACKERS": "GB",
    "TEXANS": "HOU", "COLTS": "IND", "JAGUARS": "JAX", "CHIEFS": "KC",
    "CHARGERS": "LAC", "RAMS": "LAR", "RAIDERS": "LV", "DOLPHINS": "MIA",
    "VIKINGS": "MIN", "PATRIOTS": "NE", "SAINTS": "NO", "GIANTS": "NYG",
    "JETS": "NYJ", "EAGLES": "PHI", "STEELERS": "PIT", "SEAHAWKS": "SEA",
    "49ERS": "SF", "BUCCANEERS": "TB", "TITANS": "TEN", "COMMANDERS": "WAS",
}

#: Position tokens that may prefix a name on an inactive list.
_POS = (r"QB|RB|FB|WR|TE|OL|OT|OG|G|C|DL|DT|DE|EDGE|LB|ILB|OLB|MLB|"
        r"DB|CB|S|FS|SS|K|P|LS|NT")
_ENTRY = re.compile(rf"^(?:\*|-|•)?\s*({_POS})\s+(.+?)\s*$")


class InactivesParseError(RuntimeError):
    """The bytes do not carry a parseable inactive list."""


class EmptyStatePage(InactivesParseError):
    """The bytes are the NFL.com 'check back soon' page. A PASS, but no list."""


def read_bytes(path: Path) -> str:
    """Decompress if needed and decode. Raises if the file is empty."""
    path = Path(path)
    raw = path.read_bytes()
    if not raw:
        raise InactivesParseError(f"file is empty: {path}")
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    if not raw:
        raise InactivesParseError(f"file decompressed to nothing: {path}")
    return raw.decode("utf-8", errors="replace")


def _strip_tags(doc: str) -> str:
    """HTML to visible text, preserving block boundaries as newlines.

    Block tags become newlines rather than spaces. That matters: the article
    puts each inactive in its own ``<li>``, and collapsing tags to spaces runs
    every player on one line where the entry regex cannot see them.
    """
    doc = re.sub(r"(?is)<script\b.*?</script>|<style\b.*?</style>", " ", doc)
    doc = re.sub(r"(?i)<(?:/?(?:li|ul|ol|p|div|h[1-6]|br|tr|td))\b[^>]*>", "\n", doc)
    doc = re.sub(r"(?s)<[^>]+>", " ", doc)
    return _html.unescape(doc)


def _canonical_team(line: str) -> str | None:
    """Return the team abbreviation a header line names, or None."""
    token = line.strip().strip(":").upper()
    if token in TEAM_ABBRS:
        return "ARI" if token == "AZ" else ("LAR" if token == "LA" else token)
    return NICKNAME_TO_ABBR.get(token)


def parse(document: str) -> dict[str, list[dict]]:
    """Return ``{team_abbr: [{position, name}, …]}`` from a document.

    Raises :class:`EmptyStatePage` for the landing-page shell and
    :class:`InactivesParseError` when nothing parses.
    """
    if EMPTY_STATE_MARKER in document:
        raise EmptyStatePage(
            "the document is the NFL.com empty-state page: it reports that no "
            "inactive report is published, and carries no list. A capture PASS "
            "on this page is not evidence of an inactive list."
        )

    text = _strip_tags(document) if "<" in document else document
    teams: dict[str, list[dict]] = {}
    current: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        header = _canonical_team(line)
        if header is not None:
            current = header
            teams.setdefault(current, [])
            continue
        if current is None:
            continue
        match = _ENTRY.match(line)
        if match:
            position, name = match.group(1), match.group(2).strip()
            # The article annotates the emergency QB inline. Keep the note
            # rather than discarding it, and keep it out of the name.
            note = None
            paren = re.search(r"\s*\(([^)]*)\)\s*$", name)
            if paren:
                note = paren.group(1)
                name = name[: paren.start()].strip()
            if not name or len(name) > 60:
                continue
            entry = {"position": position, "name": name}
            if note:
                entry["note"] = note
            if entry not in teams[current]:
                teams[current].append(entry)

    teams = {k: v for k, v in teams.items() if v}
    if not teams:
        raise InactivesParseError(
            "no team carried a parseable inactive entry. The document may be a "
            "hydration shell, a different layout, or the wrong page; it is not "
            "being reported as an empty inactive list."
        )
    return teams


def for_game(document: str, home: str, away: str) -> dict:
    """Parse and attribute to one game. Both teams must be present.

    A league-wide article covers every game. Finding only one of the two
    teams means the other's list is not in these bytes -- returning a
    half-attributed result would let a caller read one team's silence as
    "nobody inactive", so it raises instead.
    """
    teams = parse(document)
    missing = [t for t in (home, away) if t not in teams]
    if missing:
        raise InactivesParseError(
            f"document carries no inactive list for {', '.join(missing)}; it "
            f"names {sorted(teams)}. Absence here is not evidence that the "
            f"team has no inactives."
        )
    return {
        "contract": CONTRACT,
        "home": home,
        "away": away,
        "inactives": {home: teams[home], away: teams[away]},
        "counts": {home: len(teams[home]), away: len(teams[away])},
        "teams_in_document": sorted(teams),
        "semantics": (
            "LISTED_OFFICIAL_INACTIVE only. A player absent from this list is "
            "UNLISTED, which is not a claim that the player is active."
        ),
    }
