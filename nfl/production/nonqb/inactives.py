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


def parse(html: str, teams) -> Outcome:
    """team -> [name, ...]. Conservative, and every step re-checked downstream.

    The official page's markup is not stable enough to be worth a clever
    parser, and a clever parser that silently returns an empty list for one
    club is worse than a plain one that says so. Tags are stripped, the
    document is cut into per-team blocks at the team tokens themselves, and
    capitalised names are read a line at a time.
    """
    if not html or not html.strip():
        return Outcome.fail('INACTIVES_EMPTY_DOCUMENT',
                            'the stored document is empty')
    lines = [ln.strip() for ln in re.sub(r'<[^>]+>', '\n', html).splitlines()]
    lines = [ln for ln in lines if ln]
    marks = {}
    for i, ln in enumerate(lines):
        for t in teams:
            if re.search(rf'\b{re.escape(t)}\b', ln) and t not in marks:
                marks[t] = i
    missing = [t for t in teams if t not in marks]
    if missing:
        return Outcome.deferred(
            'INACTIVES_TEAM_NOT_REPRESENTED',
            f'{missing} do(es) not appear in the captured document, so this '
            f'capture cannot describe both clubs',
            owed={'teams_missing': missing, 'teams_found': sorted(marks)})
    order = sorted(marks.items(), key=lambda kv: kv[1])
    found = {}
    for j, (t, start) in enumerate(order):
        end = order[j + 1][1] if j + 1 < len(order) else len(lines)
        names = []
        for ln in lines[start:end]:
            for m in _NAME.finditer(ln):
                n = m.group(0).strip()
                if n not in names:
                    names.append(n)
        found[t] = names
    return Outcome.ok('INACTIVES_PARSED', value=found,
                      spec_version=SPEC_VERSION,
                      n_names={t: len(v) for t, v in found.items()},
                      block_bounds={t: [marks[t], (order[j + 1][1]
                                                   if j + 1 < len(order)
                                                   else len(lines))]
                                    for j, (t, _) in enumerate(order)})


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
