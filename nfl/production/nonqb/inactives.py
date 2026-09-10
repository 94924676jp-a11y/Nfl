"""Official gameday inactives: capture, resolve, and propagate. A4/A5.

WHAT THIS IS FOR

`weekly_rosters.status == ACT` means **on the active roster**, not **active
tonight**. Measured on the live mirror at 2026-09-10T21:08Z: SF and LA carry
105 ACT players between them and 46 will dress. Nothing in any source this
executor can reach closes that gap; the official inactives publication at about
T-90 is the only thing that does, and `nfl/ingest/eligibility.py` has carried
`PREDICTION_TIME_ELIGIBILITY_UNAVAILABLE` as an open debt for exactly this
reason.

So this module is the consumer that debt was waiting for. Before it,
`official_inactives` was captured on every pass and read by NOTHING outside the
test suite -- the bytes were collected and the football never reached a
projection.

THE ORDER IS THE POINT

    raw bytes -> hash -> store -> manifest -> identity -> sets -> propagate

Bytes are written before they are parsed, so a parser change can never make an
earlier capture unrecoverable. Identity is resolved deterministically against
the roster vintage the forecast itself consumed, and an ambiguous name is a
REFUSAL -- two players who could both be "J. Williams" is precisely where a
fuzzy match writes the wrong man onto the inactive list and nobody notices.

COMPLETENESS IS A CLAIM ABOUT BOTH CLUBS

`POST_INACTIVES_COMPLETE` is emitted only when both teams are represented. One
club's list is not most of the information; it is a forecast in which half the
players are governed by an official source and half are not, and labelling that
"complete" is the kind of half-truth this project exists to refuse.

PROPAGATION USES THE CANDIDATE'S OWN MECHANISM AND ADDS NOTHING

An inactive player's appearance draws are set to zero in every draw. Nothing
else is touched. The allocation layer already enforces
`share == 0 wherever appearance == 0` per cell, and the P4C simplex already
renormalises over the survivors. So his opportunity is redistributed by exactly
the mechanism the configuration declares -- proportional renormalisation under
every candidate today -- rather than by a redistribution rule invented here.
That is deliberate: a bespoke reallocation would be a second, undeclared model
of substitution, and Track 3 exists to test that question properly.
"""
from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import json
import pathlib
import re
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402

SPEC_VERSION = 'official-inactives-1'
VINTAGE = _REPO / 'nfl' / 'vintage'
MANIFEST = _REPO / 'nfl' / 'vintage_manifest.jsonl'
SOURCE = 'official_inactives'

COMPLETE = 'POST_INACTIVES_COMPLETE'
INCOMPLETE = 'POST_INACTIVES_INCOMPLETE'

# The eligibility vocabulary, kept apart on purpose. A designation is not a
# status and a status is not a gameday outcome.
ROSTER_ACTIVE = 'ROSTER_ACTIVE'          # on the active roster this week
GAME_ACTIVE = 'GAME_ACTIVE'              # dressing tonight
OFFICIAL_INACTIVE = 'OFFICIAL_INACTIVE'  # on tonight's official inactive list
INJURY_QUESTIONABLE = 'INJURY_QUESTIONABLE'   # a designation, not a status
UNKNOWN = 'UNKNOWN'


def _parse(t):
    if t is None:
        return None
    if isinstance(t, dt.datetime):
        return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
    d = dt.datetime.fromisoformat(str(t).replace('Z', '+00:00'))
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def _iso(d):
    return d.astimezone(dt.timezone.utc).isoformat().replace('+00:00', 'Z')


# ------------------------------------------------------------------ capture
def store(raw: bytes, *, retrieved_at, source_url, game_id,
          published_at=None, http_status=None, root=None) -> Outcome:
    """Write the bytes down BEFORE anything reads them, and hash what was written.

    Append-only and content-addressed: a re-capture of identical bytes is a new
    manifest row and no new blob, which is a MEASUREMENT that the page has not
    moved, not a no-op.
    """
    if not raw:
        return Outcome.fail(
            'INACTIVES_EMPTY_BYTES',
            'the capture returned no bytes. An empty page is an error, not an '
            'empty inactive list, and reading it as "nobody is out" is the '
            'exact absence-as-success defect this project refuses.')
    got = _parse(retrieved_at)
    if got is None:
        return Outcome.fail(
            'INACTIVES_NO_RETRIEVAL_CLOCK',
            'no retrieved_at was supplied, so the capture cannot be placed in '
            'time and its freshness cannot be established')
    digest = hashlib.sha256(raw).hexdigest()
    # `root` EXISTS SO A TEST CANNOT WRITE INTO THE LIVE VINTAGE. It already
    # did once: the first run of the propagation tests appended four rows and a
    # 70-byte blob stamped 23:05Z, and the information-set selector then chose
    # that synthetic file as tonight's inactive list. The rows were removed and
    # the blob deleted; the parameter is why it cannot recur.
    base = pathlib.Path(root) if root else _REPO
    vintage = base / 'nfl' / 'vintage' if root else VINTAGE
    manifest = (base / 'nfl' / 'vintage_manifest.jsonl') if root else MANIFEST
    vintage.mkdir(parents=True, exist_ok=True)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    blob = vintage / f'{SOURCE}.{digest[:16]}.html.gz'
    unchanged = blob.exists()
    if not unchanged:
        with gzip.GzipFile(filename='', mode='wb', fileobj=open(blob, 'wb'),
                           compresslevel=9, mtime=0) as fh:
            fh.write(raw)
    row = {'capture_id': got.strftime('%Y%m%dT%H%M%SZ'), 'source': SOURCE,
           'state': 'PASS', 'code': 'CAPTURED',
           'value': {'sha256': digest, 'n_bytes': len(raw),
                     'retrieved_at': _iso(got),
                     'published_at': _iso(_parse(published_at))
                     if published_at else None,
                     'source_url': source_url, 'game_id': game_id,
                     'http_status': http_status,
                     'blob': str(blob.relative_to(base)),
                     'content_unchanged': unchanged,
                     'spec_version': SPEC_VERSION}}
    with open(manifest, 'a') as fh:
        fh.write(json.dumps(row, sort_keys=True) + '\n')
    return Outcome.ok(
        'INACTIVES_STORED', value=str(blob.relative_to(base)),
        spec_version=SPEC_VERSION, sha256=digest, n_bytes=len(raw),
        retrieved_at=_iso(got),
        published_at=_iso(_parse(published_at)) if published_at else None,
        content_unchanged=unchanged, game_id=game_id, source_url=source_url,
        clocks_kept_apart='published_at is when the league said it; '
                          'retrieved_at is when we looked. They are different '
                          'quantities and neither substitutes for the other.')


# ------------------------------------------------------------------ parse
# NAMES DO NOT SPAN LINE BREAKS, AND THE FIRST VERSION OF THIS LET THEM.
#
# `\s+` matches a newline, so `[A-Z]\w+(\s+[A-Z]\w+)+` over a stripped list
# happily matched "Wide Starter Back Starter End Starter Ghost Player" as ONE
# name, and every real player then failed to resolve. The synthetic drill found
# it before the real list arrived, which is the whole reason the drill exists.
# Matching is line by line, and the separator is a literal space.
_NAME = re.compile(r"[A-Z][A-Za-z.'\-]+(?:[ ]+[A-Z][A-Za-z.'\-]+)+")


# A REAL INACTIVE LIST IS SHORT, AND A PAGE OF NEWS PROMOS IS NOT.
#
# The captured 2026-09-08 page (sha 88a19528350ea23f) is the empty state:
# its main content reads "Please check back soon for NFL Inactive Reports for
# this Season" and it carries NO inactive list at all. Fed to the first version
# of this parser with team tokens '49ers'/'Rams' it returned PASS with 311
# "names" -- 'NFL Week', 'Lumen Field', 'Americano NFL', 'The Seattle Seahawks'
# -- swept out of the navigation and the news tray, all attributed to one club
# and none to the other. That is the project's signature defect exactly: an
# empty result read as a populated one. Four guards below, each independent.
_EMPTY_STATE = (
    'check back soon',
    'no inactives',
    'inactives are not yet',
    'not yet available',
)

# Club identifiers, matched as WHOLE PHRASES and never as loose tokens.
#
# The first version of this rejected any candidate containing a club or city
# WORD, and the drill caught it immediately: its synthetic Rams player is
# called "Rams Runner". The real-world version of that mistake is worse --
# Justin Houston, A.J. Green, Dwayne Washington and Marshawn Lynch are all
# players whose names collide with a club token, so a token-level filter
# silently drops real inactives. Only a complete club phrase is a label.
_CLUB_PHRASES = tuple(sorted((
    'Arizona Cardinals', 'Atlanta Falcons', 'Baltimore Ravens',
    'Buffalo Bills', 'Carolina Panthers', 'Chicago Bears',
    'Cincinnati Bengals', 'Cleveland Browns', 'Dallas Cowboys',
    'Denver Broncos', 'Detroit Lions', 'Green Bay Packers',
    'Houston Texans', 'Indianapolis Colts', 'Jacksonville Jaguars',
    'Kansas City Chiefs', 'Las Vegas Raiders', 'Los Angeles Chargers',
    'Los Angeles Rams', 'Miami Dolphins', 'Minnesota Vikings',
    'New England Patriots', 'New Orleans Saints', 'New York Giants',
    'New York Jets', 'Philadelphia Eagles', 'Pittsburgh Steelers',
    'San Francisco 49ers', 'Seattle Seahawks', 'Tampa Bay Buccaneers',
    'Tennessee Titans', 'Washington Commanders',
    # Multi-word city names standing alone are labels too. Single-word cities
    # are NOT listed: "Houston" and "Washington" are surnames.
    'Green Bay', 'Kansas City', 'Las Vegas', 'Los Angeles', 'New England',
    'New Orleans', 'New York', 'San Francisco', 'Tampa Bay',
), key=len, reverse=True))

# Site chrome. Same idea, different vocabulary.
_CHROME_WORDS = frozenset("""
NFL Week Field Stadium News Video Videos Podcast Fantasy Tickets Shop Watch
Standings Schedule Scores Stats Players Teams Draft Super Bowl Network Game
Games Season Report Reports Inactive Inactives League Football Sunday Monday
Thursday Saturday Friday Tuesday Wednesday Live Highlights Analysis Top Best
Free Agents Coach Head Injury Preseason Playoffs Roster Depth Chart Sign
Subscribe Privacy Terms Policy Cookie Copyright Rights Reserved More About
Contact Careers Help Search Menu Home Latest Trending Desde Americano Ver
""".split())

# THE PAGE DOES NOT SPELL CLUBS THE WAY OUR GAME IDS DO.
#
# Our game id is 2026_01_SF_LA, so the codes handed to parse() are 'SF' and
# 'LA'. The real captured page never writes either: it writes "49ers" and
# "Rams". Matching on the code alone meant a POPULATED page would have been
# refused as INACTIVES_TEAM_NOT_REPRESENTED -- a refusal, so not a silent
# wrong answer, but it would still have cost the whole T-90 window.
_TEAM_ALIASES = {
    'ARI': ('Cardinals', 'Arizona'), 'ATL': ('Falcons', 'Atlanta'),
    'BAL': ('Ravens', 'Baltimore'), 'BUF': ('Bills', 'Buffalo'),
    'CAR': ('Panthers', 'Carolina'), 'CHI': ('Bears', 'Chicago'),
    'CIN': ('Bengals', 'Cincinnati'), 'CLE': ('Browns', 'Cleveland'),
    'DAL': ('Cowboys', 'Dallas'), 'DEN': ('Broncos', 'Denver'),
    'DET': ('Lions', 'Detroit'), 'GB': ('Packers', 'Green Bay'),
    'HOU': ('Texans', 'Houston'), 'IND': ('Colts', 'Indianapolis'),
    'JAX': ('Jaguars', 'Jacksonville'), 'KC': ('Chiefs', 'Kansas City'),
    'LV': ('Raiders', 'Las Vegas'), 'LAC': ('Chargers',),
    'LA': ('Rams', 'Los Angeles Rams'), 'LAR': ('Rams', 'Los Angeles Rams'),
    'MIA': ('Dolphins', 'Miami'), 'MIN': ('Vikings', 'Minnesota'),
    'NE': ('Patriots', 'New England'), 'NO': ('Saints', 'New Orleans'),
    'NYG': ('Giants', 'New York Giants'), 'NYJ': ('Jets', 'New York Jets'),
    'PHI': ('Eagles', 'Philadelphia'), 'PIT': ('Steelers', 'Pittsburgh'),
    'SF': ('49ers', 'San Francisco'), 'SEA': ('Seahawks', 'Seattle'),
    'TB': ('Buccaneers', 'Tampa Bay'), 'TEN': ('Titans', 'Tennessee'),
    'WAS': ('Commanders', 'Washington'),
}


def _team_tokens(team: str):
    """The code itself first, then the spellings the page actually uses."""
    return (team,) + tuple(_TEAM_ALIASES.get(team.upper(), ()))


def _marks(teams, lines):
    """First line mentioning each club, under any spelling it may use."""
    marks = {}
    for i, ln in enumerate(lines):
        for t in teams:
            if t in marks:
                continue
            if any(re.search(rf'\b{re.escape(tok)}\b', ln)
                   for tok in _team_tokens(t)):
                marks[t] = i
    return marks


# The rule the league itself imposes: a club dresses 48 of a 53-man roster, so
# an inactive list is about 5 to 8 names. Anything past a dozen is not a list,
# it is a page.
_MAX_PER_TEAM = 12


def _plausible_person(name: str) -> bool:
    """Is this candidate shaped like a player's name rather than a label?

    Deliberately permissive about people and strict about labels. A real
    inactive wrongly dropped here is invisible downstream; a label wrongly
    kept is caught by the size ceiling and again by identity resolution.
    """
    toks = name.split()
    if not 2 <= len(toks) <= 4:
        return False
    if len(name) > 32:
        return False
    if any(ch.isdigit() for ch in name):
        return False
    bare = re.sub(r'^The\s+', '', name).strip()
    for phrase in _CLUB_PHRASES:
        if phrase in bare:
            return False
    stripped = [t.strip(".,'-") for t in toks]
    if any(t in _CHROME_WORDS for t in stripped):
        return False
    return True


def parse(html: str, teams) -> Outcome:
    """team -> [name, ...]. Conservative, and every step re-checked downstream.

    THIS PARSER HAS NEVER SEEN A POPULATED PAGE, AND SAYS SO BY REFUSING.

    Every captured example in this repository is the empty state. The markup
    of a populated list is therefore unknown, and a segmenter tuned against a
    document I wrote myself would be fitted to my own assumptions rather than
    to the league's HTML. So this reads the plain shape -- tags stripped, the
    document cut at the club tokens, capitalised names a line at a time -- and
    leans hard on refusing. A refusal is cheap and recoverable; a list
    assembled out of page furniture is neither.

    When it refuses on bytes that plainly do carry the lists, the operator
    path is `verify_supplied_names`, which takes the names explicitly and
    checks every one of them back against these same stored bytes.
    """
    if not html or not html.strip():
        return Outcome.fail('INACTIVES_EMPTY_DOCUMENT',
                            'the stored document is empty')
    lines = [ln.strip() for ln in re.sub(r'<[^>]+>', '\n', html).splitlines()]
    lines = [ln for ln in lines if ln]

    # GUARD 1 -- the page's own empty state. It says so; believe it.
    flat = ' '.join(lines).lower()
    for marker in _EMPTY_STATE:
        if marker in flat:
            return Outcome.deferred(
                'INACTIVES_PAGE_EMPTY_STATE',
                f'the captured page carries its own empty-state text '
                f'({marker!r}), so it publishes no inactive list yet. This is '
                f'a real page and a real fetch; it simply has no content, and '
                f'reading names out of its navigation would manufacture a list',
                owed={'empty_state_marker': marker, 'n_lines': len(lines)})

    marks = _marks(teams, lines)
    missing = [t for t in teams if t not in marks]
    if missing:
        return Outcome.deferred(
            'INACTIVES_TEAM_NOT_REPRESENTED',
            f'{missing} do(es) not appear in the captured document, so this '
            f'capture cannot describe both clubs',
            owed={'teams_missing': missing, 'teams_found': sorted(marks),
                  'tokens_tried': {t: list(_team_tokens(t)) for t in teams}})

    order = sorted(marks.items(), key=lambda kv: kv[1])
    found, rejected = {}, {}
    for j, (t, start) in enumerate(order):
        end = order[j + 1][1] if j + 1 < len(order) else len(lines)
        names, drops = [], []
        for ln in lines[start:end]:
            for m in _NAME.finditer(ln):
                n = m.group(0).strip()
                if n in names or n in drops:
                    continue
                (names if _plausible_person(n) else drops).append(n)
        found[t], rejected[t] = names, drops

    # GUARD 2 -- a club with no names is not an answer for that club.
    empty = [t for t, v in found.items() if not v]
    if empty:
        return Outcome.deferred(
            'INACTIVES_TEAM_HAS_NO_NAMES',
            f'the club(s) {empty} appear in the captured document but no '
            f'player-shaped name was found in their block, so this capture '
            f'does not carry a list for them',
            owed={'teams_without_names': empty,
                  'n_names': {t: len(v) for t, v in found.items()},
                  'n_rejected_as_labels': {t: len(v)
                                           for t, v in rejected.items()}})

    # GUARD 3 -- an implausibly long block means chrome was swept in.
    oversize = {t: len(v) for t, v in found.items() if len(v) > _MAX_PER_TEAM}
    if oversize:
        return Outcome.deferred(
            'INACTIVES_BLOCK_IMPLAUSIBLY_LARGE',
            f'{oversize} name(s) were read for those clubs against a ceiling '
            f'of {_MAX_PER_TEAM}. A club dresses 48 of 53, so a real inactive '
            f'list is roughly 5 to 8 names; a block this size means the '
            f'document was swept rather than parsed',
            owed={'n_names': {t: len(v) for t, v in found.items()},
                  'ceiling': _MAX_PER_TEAM,
                  'sample': {t: v[:10] for t, v in found.items()}})

    return Outcome.ok('INACTIVES_PARSED', value=found,
                      spec_version=SPEC_VERSION,
                      segmentation='machine_read_from_bytes',
                      n_names={t: len(v) for t, v in found.items()},
                      n_rejected_as_labels={t: len(v)
                                            for t, v in rejected.items()},
                      rejected_sample={t: v[:8] for t, v in rejected.items()},
                      block_bounds={t: [marks[t], (order[j + 1][1]
                                                   if j + 1 < len(order)
                                                   else len(lines))]
                                    for j, (t, _) in enumerate(order)})


def verify_supplied_names(html: str, names_by_team) -> Outcome:
    """Accept per-club names given explicitly, but only if the BYTES say so.

    WHY THIS EXISTS, AND WHY IT IS NOT A BACK DOOR.

    `parse()` refuses on any document whose shape it cannot read, and it has
    never seen a populated page, so it may well refuse bytes that plainly do
    carry both lists. Without a path forward that would mean the window closes
    on a parser limitation rather than on missing information.

    The path is not "type in what you believe". Every supplied name must occur
    VERBATIM in the stored official document. A name that is not in the bytes
    is rejected by code, so a reporter's expectation, a sportsbook's implied
    starter or a remembered list cannot be entered here -- they would have to
    already be in the league's own page to pass, and if they are in the page
    they are the league's words and not the operator's.

    What the operator supplies is the SEGMENTATION -- which names belong to
    which club -- not the information. The artifact records it as such, so a
    later reader can tell a machine reading from an assisted one and can
    re-check every name against the same stored hash.
    """
    if not html or not html.strip():
        return Outcome.fail('INACTIVES_EMPTY_DOCUMENT',
                            'the stored document is empty')
    if not names_by_team or not all(names_by_team.get(t)
                                    for t in names_by_team):
        return Outcome.fail(
            'INACTIVES_SUPPLIED_LIST_INCOMPLETE',
            'every club must be given at least one name; a club with an '
            'empty list is a missing answer, not an empty one',
            owed={'supplied': {t: len(v or [])
                               for t, v in (names_by_team or {}).items()}})
    absent = {}
    for team, names in names_by_team.items():
        gone = [n for n in names if n not in html]
        if gone:
            absent[team] = gone
    if absent:
        return Outcome.fail(
            'INACTIVES_SUPPLIED_NAME_NOT_IN_BYTES',
            f'{sum(len(v) for v in absent.values())} supplied name(s) do not '
            f'occur in the stored official document, so they did not come '
            f'from it. Nothing is accepted from this call',
            owed={'names_not_in_document': absent})
    oversize = {t: len(v) for t, v in names_by_team.items()
                if len(v) > _MAX_PER_TEAM}
    if oversize:
        return Outcome.fail(
            'INACTIVES_BLOCK_IMPLAUSIBLY_LARGE',
            f'{oversize} against a ceiling of {_MAX_PER_TEAM}',
            owed={'ceiling': _MAX_PER_TEAM})
    return Outcome.ok(
        'INACTIVES_PARSED', value={t: list(v) for t, v in
                                   names_by_team.items()},
        spec_version=SPEC_VERSION,
        segmentation='operator_supplied_verified_against_bytes',
        n_names={t: len(v) for t, v in names_by_team.items()},
        every_name_found_verbatim_in_document=True)


# --------------------------------------------------------------- identity
def resolve(names_by_team, roster) -> Outcome:
    """Map every name to exactly one gsis_id, or refuse.

    `roster` is {gsis_id: {'name':..., 'team':...}} from the SAME vintage the
    forecast consumed, so an inactive list cannot silently describe a different
    roster from the projections it is about to zero.
    """
    idx = {}
    for pid, r in roster.items():
        nm = (r.get('name') or '').strip()
        if not nm:
            continue
        idx.setdefault((r.get('team'), _key(nm)), []).append(pid)
    out, unmapped, ambiguous = {}, [], {}
    for t, names in names_by_team.items():
        got = []
        for n in names:
            hits = idx.get((t, _key(n)), [])
            if len(hits) == 1:
                got.append(hits[0])
            elif len(hits) > 1:
                ambiguous[f'{t}:{n}'] = hits
            else:
                unmapped.append(f'{t}:{n}')
        out[t] = got
    if ambiguous:
        return Outcome.fail(
            'INACTIVES_IDENTITY_AMBIGUOUS',
            f'{len(ambiguous)} name(s) match more than one rostered player. '
            f'Fuzzy resolution is forbidden: writing the wrong man onto an '
            f'inactive list zeroes the wrong projection and nothing downstream '
            f'would object.', ambiguous=dict(list(ambiguous.items())[:10]))
    return Outcome.ok('INACTIVES_RESOLVED', value=out,
                      spec_version=SPEC_VERSION,
                      n_resolved={t: len(v) for t, v in out.items()},
                      n_unmapped=len(unmapped), unmapped=unmapped[:20],
                      unmapped_meaning='a name on the page with no rostered '
                                       'match. Reported, never guessed.')


def _key(n):
    return re.sub(r'[^a-z]', '', (n or '').lower())


# ------------------------------------------------------------------ sets
def sets(resolved, roster, teams, *, retrieved_at, kickoff_utc,
         game_id) -> Outcome:
    """The OFFICIAL_INACTIVE set, and what the source does NOT establish.

    OWNER RULING 2026-09-10 item 4, and the reason this function no longer
    returns anything called `active`.

    The inactives publication is an assertion about who is OUT. It is not an
    assertion that everybody else is dressing. A roster carries 52-53 names,
    about 48 dress, and roughly 7 are listed inactive -- so "not on the list"
    covers players who will dress AND practice-squad members who were never
    going to, and the page does not distinguish them. Returning a set called
    `active` invited exactly the inference the ruling forbids: that a pregame
    `ACT` plus an absence from the list equals GAME_ACTIVE.

    So the second set is named `not_listed_inactive` and carries no positive
    claim. Its members keep whatever status the roster gave them --
    ROSTER_ACTIVE for `ACT`, and nothing stronger.

    Chronology first: a list retrieved at or after kickoff is not pregame
    information about who would dress, and is refused rather than used.
    """
    got, ko = _parse(retrieved_at), _parse(kickoff_utc)
    if got is None or ko is None:
        return Outcome.fail('INACTIVES_NO_CLOCK',
                            'both a retrieval clock and a kickoff are needed '
                            'to establish that this list is pregame')
    if got >= ko:
        return Outcome.fail(
            'INACTIVES_POST_KICKOFF',
            f'the list was retrieved at {_iso(got)}, at or after kickoff '
            f'{_iso(ko)}. That is not pregame information.',
            retrieved_at=_iso(got), kickoff_utc=_iso(ko))
    missing = [t for t in teams if not resolved.get(t)]
    flagged = set()
    for t in teams:
        flagged.update(resolved.get(t) or [])
    inactive, not_listed = {}, {}
    for pid, r in roster.items():
        if r.get('team') not in teams:
            continue
        (inactive if pid in flagged else not_listed)[pid] = r.get('team')
    label = INCOMPLETE if missing else COMPLETE
    ev = {'game_id': game_id, 'label': label,
          'n_official_inactive': len(inactive),
          'n_not_listed_inactive': len(not_listed),
          'what_not_listed_means':
              'ABSENCE FROM THE LIST, AND NOTHING MORE. The publication says '
              'who is out; it does not say the rest are dressing. These '
              'players keep the status the roster gave them and receive no '
              'GAME_ACTIVE designation from this source.',
          'inactive_by_team': {t: sorted(p for p, tt in inactive.items()
                                         if tt == t) for t in teams},
          'n_inactive_by_team': {t: sum(1 for tt in inactive.values()
                                        if tt == t) for t in teams},
          'teams_without_a_list': missing,
          'retrieved_at': _iso(got), 'kickoff_utc': _iso(ko),
          'hours_before_kickoff': round(
              (ko - got).total_seconds() / 3600.0, 3),
          'spec_version': SPEC_VERSION}
    if missing:
        return Outcome.deferred(
            INCOMPLETE,
            f'{missing} has no resolved inactive list, so the game is not '
            f'covered on both sides and the run may not be labelled '
            f'{COMPLETE}. Half a governed forecast is not a governed forecast.',
            owed={'teams': missing}, **ev)
    return Outcome.ok(
        COMPLETE,
        value={'inactive': inactive, 'not_listed_inactive': not_listed,
               'states': {**{p: OFFICIAL_INACTIVE for p in inactive},
                          **{p: ROSTER_ACTIVE for p in not_listed}}},
        **ev)


# ------------------------------------------------------------- propagation
def apply_to_appearance(draws: dict, inactive_ids) -> Outcome:
    """Zero the appearance draws of every inactive player. Nothing else moves.

    Returning the same object mutated would make the before/after comparison
    this repair is judged by impossible, so a new mapping is built.
    """
    ids = set(inactive_ids or ())
    if not ids:
        return Outcome.not_applicable(
            'INACTIVES_NONE_SUPPLIED',
            'no inactive player was supplied, so no appearance draw was '
            'zeroed. Reported rather than treated as a successful application '
            'of an empty list.')
    out, zeroed, absent = {}, [], []
    for pid, v in draws.items():
        a = np.asarray(v)
        if pid in ids:
            out[pid] = np.zeros_like(a)
            zeroed.append(pid)
        else:
            out[pid] = a
    for pid in sorted(ids):
        if pid not in draws:
            absent.append(pid)
    return Outcome.ok(
        'INACTIVES_APPLIED', value=out, spec_version=SPEC_VERSION,
        n_zeroed=len(zeroed), zeroed=sorted(zeroed),
        n_inactive_not_in_the_draw_set=len(absent),
        not_in_draw_set=absent[:20],
        redistribution='NONE APPLIED HERE. The allocation layer enforces '
                       'share == 0 wherever appearance == 0, and the P4C '
                       'simplex renormalises over the survivors, so the '
                       'opportunity moves by the configuration\'s own declared '
                       'mechanism and by nothing added here.')
