"""Parser for the official NFL injury report. G0A item 1, proof point 7.

BUILT FROM CAPTURED BYTES, NOT FROM REMEMBERED STRUCTURE

Every selector below was read out of a real captured artifact
(`official_injury_report.9d7bb2f6479e6402.html.gz`, 328,961 bytes, retrieved
2026-09-07). Nothing here is recalled page structure and nothing is an invented
schema. That ordering was deliberate: the capture came first precisely so the
parser could be written against evidence.

THE RAW ARTIFACT IS AUTHORITATIVE AND THIS IS DOWNSTREAM

The parser never writes to the artifact and never returns it modified. Every
parsed record carries the sha256 of the bytes it came from, so a record can
always be traced back and re-derived by a later parser.

WHAT THE PAGE ACTUALLY SUPPORTS, MEASURED

  season, week   `<option value="/injuries/league/2026/reg1" selected>`, and
                 independently the <title>. Both must agree or attribution is
                 refused -- one signal is a claim, two agreeing is evidence.
  team           the matchup strip carries BOTH the abbreviation and the full
                 name, adjacent. So the document supplies its own name->abbr
                 map and this module does not invent one. An unknown name is
                 TEAM_UNMAPPED, never guessed.
  game           each matchup strip names exactly two teams. A row's team must
                 belong to the pair its table sits under.
  player         a profile slug and a display name. There is NO gsis_id on the
                 page, so every row is PLAYER_UNMAPPED against the project's
                 identifier spine until a crosswalk resolves it. That is a debt,
                 not a defect, and it is not closed by name matching.

WHAT IT DOES NOT CONSUME, AND ONE CORRECTION

CORRECTION, 2026-09-07. An earlier version of this docstring said the page
carries "no kickoff time, no game date". That was wrong and was written from
the visible markup rather than the whole artifact. The page embeds a broadcast
listing payload carrying `"StartTime":"2026-09-10T00:20:00.000Z"`, an `EndTime`,
and a `GameId` UUID -- 79 such entries against the 16 matchup strips the injury
tables are organised by.

Parser 1.0.0 deliberately does not consume it, and the reason is the 79-vs-16
mismatch: the correspondence between that payload and the report tables is not
stated anywhere on the page, so joining them would be an assumption presented as
a field. `GameId` is also a broadcast UUID, not a gsis or nflverse identifier,
so it does not resolve the identifier debt either. Establishing that join is
open work, recorded here rather than guessed at.

What the page genuinely does not carry is any gsis identifier: measured, zero
matches for the `00-0NNNNNN` pattern across the whole artifact. So the player
identifier debt is real and is not closed by reading further.
"""
from __future__ import annotations

import dataclasses
import hashlib
import html as _html
import json
import pathlib
import re
import sys
from typing import Optional

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from nfl.identity.effective_scope import Authority  # noqa: E402

# Bumping this changes downstream transformation identity. Parsed records carry
# it, so records produced by two parser versions are never silently pooled.
PARSER_VERSION = "official_injury_report/1.0.0"

# Structures the page MUST have. Absence is drift, not an empty result -- a
# parser that returns [] against changed markup produces plausible-looking
# nothing, which is worse than failing.
_REQUIRED_STRUCTURE = {
    "week_option": re.compile(
        r'<option value="/injuries/league/(?P<season>\d{4})/'
        r'(?P<type>[a-z]+)(?P<week>\d+)"\s+selected>'),
    "title_week": re.compile(
        r'<title>[^<]*Week\s+(?P<week>\d+)\s+of the\s+(?P<season>\d{4})\s+Season',
        re.I),
    "matchup_abbr": re.compile(
        r'nfl-c-matchup-strip__team-abbreviation">\s*([A-Z]{2,3})\s*<'),
    "matchup_fullname": re.compile(
        r'nfl-c-matchup-strip__team-fullname"[^>]*>\s*([^<]+?)\s*</a>'),
    "section_title": re.compile(
        r'd3-o-section-sub-title"><span>([^<]+)</span>'),
    "report_table": re.compile(
        r'<table class="d3-o-table d3-o-table--detailed d3-o-reports--detailed">'),
    # A truncated transfer is the Class A failure in its purest form: the
    # injury tables sit early in this document, so half a page parses to a
    # perfectly plausible eleven rows. Requiring the closing tag is the
    # cheapest available check that the bytes we hold are the whole response.
    "document_close": re.compile(r"</html>\s*$"),
}

_EXPECTED_HEADERS = ["Player", "Position", "Injuries",
                     "Practice Status", "Game Status"]

_ROW_RE = re.compile(r"<tr>(.*?)</tr>", re.S)
_CELL_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
_SLUG_RE = re.compile(r'href="/players/([a-z0-9\-]+)/"')
_TAG_RE = re.compile(r"<[^>]+>")


def _text(fragment: str) -> str:
    return _html.unescape(_TAG_RE.sub("", fragment)).strip()


def transformation_identity(raw_sha256: str, parser_version: str) -> str:
    """The identity of a PARSE, which is the artifact plus the code that read it.

    Two records over the same bytes from two parser versions are two different
    derivations and must not pool. MLB M0 is the counter-example that motivates
    this: `SIM_FORMULA` excluded the corpus, so substituting the input left the
    fingerprint identical and nothing could detect it. Here the parser version
    is INSIDE the identity rather than recorded beside it, so a version bump
    necessarily changes every downstream record id.
    """
    if not raw_sha256 or len(raw_sha256) != 64:
        raise ValueError(
            f"transformation_identity needs the full 64-char artifact digest, "
            f"got {raw_sha256!r}. A truncated hash cannot identify bytes.")
    if not parser_version:
        raise ValueError("transformation_identity needs a parser version.")
    blob = json.dumps({"raw_sha256": raw_sha256,
                       "parser_version": parser_version},
                      sort_keys=True, separators=(",", ":")).encode()
    return "NFLTX-" + hashlib.sha256(blob).hexdigest()[:16]


class AuthorityViolation(RuntimeError):
    """Raised when a record claims more authority than its evidence permits."""


# Keys that describe the derivation itself rather than being derived values.
_DERIVATION_META = frozenset({"method", "evidence", "authority"})


@dataclasses.dataclass(frozen=True)
class ParsedRow:
    """One player-row, with its provenance kept in separate compartments.

    `source_provided` is what the page literally said. `normalized` is what we
    mapped it to, using a map the page itself supplied. `derived` is anything
    inferred, with its method and evidence attached. They are never merged,
    because merging them makes it impossible to tell later what the source
    guaranteed from what we concluded.

    The compartment rule is enforced at construction, not by convention. A
    derived value wearing source authority is unfalsifiable downstream: nothing
    later in the pipeline can tell that the page never said it.
    """
    raw_sha256: str
    parser_version: str
    source_provided: dict
    normalized: dict
    derived: dict
    refusals: tuple
    transformation_id: str = ""

    def __post_init__(self):
        if not self.raw_sha256 or len(self.raw_sha256) != 64:
            raise AuthorityViolation(
                f"RECORD_UNTRACEABLE: raw_sha256 {self.raw_sha256!r} is not a "
                f"full 64-char digest. A record that cannot name the exact "
                f"bytes it came from cannot be re-derived or audited.")

        auth = self.derived.get("authority")
        if auth is None:
            raise AuthorityViolation(
                "DERIVATION_AUTHORITY_UNDECLARED: a derived compartment with "
                "no authority class is a claim with no strength attached.")
        try:
            auth = Authority(auth)
        except ValueError:
            raise AuthorityViolation(
                f"DERIVATION_AUTHORITY_UNKNOWN: {auth!r} is not one of "
                f"{[a.value for a in Authority]}.")
        if auth is Authority.SOURCE_PROVIDED:
            raise AuthorityViolation(
                "DERIVED_PRESENTED_AS_SOURCE: the derived compartment cannot "
                "claim SOURCE_PROVIDED. If the page literally said it, it "
                "belongs in source_provided; if we concluded it, it is derived "
                "and must carry a derived authority class.")
        if not self.derived.get("method") or not self.derived.get("evidence"):
            raise AuthorityViolation(
                "DERIVATION_UNEVIDENCED: a derived value must carry both the "
                "method that produced it and the evidence it rests on.")

        overlap = ((set(self.derived) - _DERIVATION_META)
                   & set(self.source_provided))
        if overlap:
            raise AuthorityViolation(
                f"COMPARTMENT_COLLISION: {sorted(overlap)} appear in both "
                f"source_provided and derived, so a reader cannot tell which "
                f"compartment guaranteed the value.")

        object.__setattr__(self, "transformation_id",
                           transformation_identity(self.raw_sha256,
                                                   self.parser_version))

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)


def _drift(missing: list, detail: str = "") -> Outcome:
    return Outcome.fail(
        "PARSER_SCHEMA_DRIFT",
        f"required page structure absent: {missing}. The page changed shape. "
        f"Returning an empty parse here would produce plausible-looking nothing "
        f"and silently discharge a capture obligation; the raw bytes are "
        f"retained so a future parser can reprocess this artifact. {detail}",
        missing=missing, parser_version=PARSER_VERSION)


def parse(raw: bytes, *, raw_sha256: str,
          capture_scope: Optional[dict] = None) -> Outcome:
    """Parse a captured injury-report page. Never mutates `raw`."""
    if not raw:
        return Outcome.fail(
            "PARSER_INPUT_EMPTY",
            "no bytes supplied. An empty input is not an empty report.",
            parser_version=PARSER_VERSION)

    actual = hashlib.sha256(raw).hexdigest()
    if raw_sha256 and not actual.startswith(raw_sha256[:16]):
        return Outcome.fail(
            "RAW_SHA256_MISMATCH",
            f"the bytes hash to {actual[:16]} but were presented as "
            f"{raw_sha256[:16]}. A parsed record must be traceable to the exact "
            f"artifact it came from.",
            expected=raw_sha256[:16], actual=actual[:16])

    # --- the capture this parse claims to be OF ------------------------------
    # A parse carries the vintage of the bytes it read, never a vintage handed
    # to it. Presenting Tuesday's practice report under Sunday's inactives
    # timestamp is not a parsing error the reader could notice: both parse
    # cleanly, and the resulting record is wrong about when it was true.
    if capture_scope is not None:
        claimed = (capture_scope.get("sha256")
                   or capture_scope.get("raw_sha256")
                   or capture_scope.get("content_sha256"))
        if claimed is None:
            return Outcome.blocked(
                "CAPTURE_SCOPE_UNIDENTIFIED",
                "a capture scope was supplied that does not name the bytes it "
                "describes, so it cannot be checked against them. An "
                "unverifiable scope is not weaker evidence, it is none.",
                cause=Cause.DATA, keys=sorted(capture_scope))
        if claimed != actual:
            return Outcome.fail(
                "VINTAGE_MISREPRESENTED",
                f"the supplied capture scope describes artifact "
                f"{claimed[:16]} but these bytes are {actual[:16]}. Attaching "
                f"one capture's timestamps to another capture's content "
                f"backdates or postdates every row in it.",
                claimed=claimed, actual=actual)

    text = raw.decode("utf-8", "replace")
    flat = re.sub(r"\s+", " ", text)

    missing = [k for k, rx in _REQUIRED_STRUCTURE.items() if not rx.search(flat)]
    if missing:
        return _drift(missing)

    # --- season / week: two independent signals that must agree --------------
    opt = _REQUIRED_STRUCTURE["week_option"].search(flat)
    ttl = _REQUIRED_STRUCTURE["title_week"].search(flat)
    o_season, o_week, o_type = (int(opt.group("season")),
                                int(opt.group("week")), opt.group("type"))
    t_season, t_week = int(ttl.group("season")), int(ttl.group("week"))
    if (o_season, o_week) != (t_season, t_week):
        return Outcome.fail(
            "AMBIGUOUS_ATTRIBUTION",
            f"the selected week option says {o_season} week {o_week} and the "
            f"title says {t_season} week {t_week}. Two signals disagree, so "
            f"neither is evidence. Refusing rather than choosing one.",
            option=(o_season, o_week), title=(t_season, t_week))

    # --- the page's OWN team map, not one we brought with us -----------------
    abbrs = _REQUIRED_STRUCTURE["matchup_abbr"].findall(flat)
    fulls = _REQUIRED_STRUCTURE["matchup_fullname"].findall(flat)
    if len(abbrs) != len(fulls):
        return _drift(["matchup_abbr/fullname pairing"],
                      f"{len(abbrs)} abbreviations against {len(fulls)} names")
    if len(abbrs) % 2:
        return _drift(["matchup pairing"],
                      f"{len(abbrs)} teams in matchup strips is not even")
    name_to_abbr: dict = {}
    for a, f in zip(abbrs, fulls):
        f = _html.unescape(f).strip()
        if f in name_to_abbr and name_to_abbr[f] != a:
            return Outcome.fail(
                "AMBIGUOUS_ATTRIBUTION",
                f"team name {f!r} maps to both {name_to_abbr[f]!r} and {a!r} on "
                f"the same page.", team=f)
        name_to_abbr[f] = a
    games = [(abbrs[i], abbrs[i + 1]) for i in range(0, len(abbrs), 2)]

    # --- tables, each preceded by the section title naming its team ----------
    rows: list = []
    refusals_seen: list = []
    for tmatch in _REQUIRED_STRUCTURE["report_table"].finditer(flat):
        before = flat[:tmatch.start()]
        sec = _REQUIRED_STRUCTURE["section_title"].findall(before)
        if not sec:
            refusals_seen.append("TEAM_UNMAPPED")
            continue
        team_name = _html.unescape(sec[-1]).strip()
        section_index = len(sec) - 1

        tbl_end = flat.find("</table>", tmatch.end())
        table = flat[tmatch.end():tbl_end if tbl_end != -1 else None]

        headers = [_text(h) for h in
                   re.findall(r"<th[^>]*>(.*?)</th>", table, re.S)]
        if headers != _EXPECTED_HEADERS:
            return _drift(["table headers"],
                          f"expected {_EXPECTED_HEADERS}, got {headers}")

        team_abbr = name_to_abbr.get(team_name)
        row_refusals = []
        if team_abbr is None:
            row_refusals.append("TEAM_UNMAPPED")

        # Section order pairs with matchup order: sections 0,1 -> game 0.
        game_index = section_index // 2
        game = games[game_index] if game_index < len(games) else None
        if game is None:
            row_refusals.append("GAME_UNMAPPED")
        elif team_abbr is not None and team_abbr not in game:
            # The one that must never be waved through: a team's rows landing
            # under a game it is not playing in.
            row_refusals.append("AMBIGUOUS_ATTRIBUTION")

        # A player listed twice under one team is two different claims about
        # the same person's status. Neither can be preferred, so both are
        # marked rather than one being silently kept.
        table_slugs = _SLUG_RE.findall(table)
        duplicated = {sl for sl in table_slugs if table_slugs.count(sl) > 1}

        for rmatch in _ROW_RE.finditer(table):
            cells = _CELL_RE.findall(rmatch.group(1))
            if not cells:
                continue                      # the header row
            if len(cells) != len(_EXPECTED_HEADERS):
                return _drift(["row cell count"],
                              f"{len(cells)} cells against "
                              f"{len(_EXPECTED_HEADERS)} headers")
            slug = _SLUG_RE.search(cells[0])
            player_name = _text(cells[0])
            r_ref = list(row_refusals)
            if not slug:
                r_ref.append("PLAYER_UNMAPPED")
            elif slug.group(1) in duplicated:
                r_ref.append("AMBIGUOUS_ATTRIBUTION")
            # There is no gsis_id anywhere on this page, so EVERY row is
            # unmapped against the project's identifier spine. Name matching is
            # refused: measured on the six real unmapped MLB players it recovers
            # two, SILENTLY MIS-JOINS two, and fails two.
            r_ref.append("PLAYER_GSIS_UNMAPPED")
            refusals_seen.extend(r_ref)

            rows.append(ParsedRow(
                raw_sha256=actual,
                parser_version=PARSER_VERSION,
                source_provided={
                    "team_full_name": team_name,
                    "player_display_name": player_name,
                    "player_profile_slug": slug.group(1) if slug else None,
                    "position": _text(cells[1]),
                    "injuries": _text(cells[2]) or None,
                    "practice_status": _text(cells[3]) or None,
                    "game_status": _text(cells[4]) or None,
                },
                normalized={
                    "team_abbr": team_abbr,
                    "season": o_season,
                    "week": o_week,
                    "season_type": o_type,
                },
                derived={
                    "game_teams": list(game) if game else None,
                    "method": ("team from the page's own matchup-strip "
                               "name->abbreviation map; game by pairing the "
                               "section index with the matchup index; season "
                               "and week from the selected option, "
                               "cross-checked against the title"),
                    "evidence": {
                        "selected_option": f"/injuries/league/{o_season}/"
                                           f"{o_type}{o_week}",
                        "title_agrees": True,
                        "section_index": section_index,
                        "game_index": game_index,
                    },
                    "authority": "DERIVED_DETERMINISTIC",
                },
                refusals=tuple(r_ref),
            ))

    if not rows:
        # The page had every required structure and yielded nothing. That is a
        # real possibility early in a week, but it must not look like success.
        return Outcome.not_applicable(
            "NO_REPORT_ROWS_PUBLISHED",
            f"{o_season} week {o_week}: page structure intact, "
            f"{len(games)} games listed, and no player rows published yet. "
            f"This is the expected state before the first practice report, and "
            f"it discharges nothing.",
            season=o_season, week=o_week, n_games=len(games),
            parser_version=PARSER_VERSION)

    return Outcome.ok(
        "REPORT_PARSED", value=rows,
        detail=f"{len(rows)} rows, {o_season} week {o_week}, "
               f"{len(games)} games; refusals: "
               f"{sorted(set(refusals_seen))}",
        n_rows=len(rows), season=o_season, week=o_week,
        parser_version=PARSER_VERSION, raw_sha256=actual,
        capture_scope=capture_scope)


def discharges_capture_obligation(parse_outcome: Outcome, kind: str, *,
                                  manifest_path=None,
                                  source: str = "official_injury_report"
                                  ) -> Outcome:
    """Does a successful parse close a scheduler obligation? Almost never.

    A parse is a transformation of bytes we already hold. It creates no new
    evidence about the world, so it cannot by itself mean a capture happened.
    The obligation is discharged by an authorised raw PASS in the manifest and
    by nothing else; this function exists so that the claim has to be made
    explicitly and can be refused.

    The failure this prevents is the cheap one: reprocess an old artifact,
    watch the parser return PASS, and let the green tick be read as "we have
    this week's report".
    """
    from nfl.capture.registry import can_discharge, unmet_targets

    if parse_outcome.state is not State.PASS:
        return Outcome.blocked(
            "OBLIGATION_NOT_DISCHARGED",
            f"the parse itself is {parse_outcome.state.value}"
            f"[{parse_outcome.code}], so there is nothing to argue about.",
            cause=Cause.DEPENDENCY, kind=kind)

    if not can_discharge(source, kind):
        return Outcome.blocked(
            "SOURCE_NOT_AUTHORISED_FOR_KIND",
            f"{source} is not authorised to serve {kind!r}, so no parse of it "
            f"discharges that obligation however clean the parse is.",
            cause=Cause.GOVERNANCE, kind=kind, source=source)

    unmet = unmet_targets(manifest_path)
    if kind in unmet["unmet"]:
        return Outcome.blocked(
            "OBLIGATION_NOT_DISCHARGED",
            f"the parse succeeded, but no authorised raw capture of {kind!r} "
            f"is recorded in the manifest. Parsing bytes we already held is a "
            f"transformation, not an observation: it produces no new evidence "
            f"that the source published anything, and it must not be allowed "
            f"to close a perishable capture window.",
            cause=Cause.DEPENDENCY, kind=kind,
            manifest_evidence=unmet["evidence"],
            captured_sources=unmet["captured_sources"])

    return Outcome.ok(
        "OBLIGATION_DISCHARGED_BY_RAW_CAPTURE",
        value={"kind": kind, "source": source,
               "raw_sha256": parse_outcome.evidence.get("raw_sha256")},
        detail=f"{kind} is met by a recorded raw PASS from an authorised "
               f"source; the parse is downstream of that, not the reason for "
               f"it.",
        kind=kind)
