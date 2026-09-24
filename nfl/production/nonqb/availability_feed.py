"""Current-state availability evidence, graded and ranked by authority.

WHAT WAS WRONG. The appearance mechanism consumes one source: the nflverse
`injuries` CSV captures. Every 2026 capture carries WEEK 1 ONLY -- 769 rows
across eight blobs, zero for week 2 -- so `n_with_an_injuries_row` is 0 for
every player on a week-2 board. Meanwhile 428 ESPN captures sit in the same
vintage directory; the newest lawful at a 2026-09-16 cutoff is stamped
2026-09-15T13:06Z and lists Ty Johnson OUT with a hamstring while the board
gave him 4.1 carries.

Two transformations stopped it:
  (a) `readiness.lawful_injuries_rows` selects `lawful_paths('injuries', ...)`
      -- a different source name was never offered;
  (b) `appearance_model.parse_injuries_rows` requires an integer season AND
      week per row, and a current-state feed carries neither, so every row
      would have been dropped by a bare `continue` even if offered.

AUTHORITY IS RANKED AND THIS FEED DOES NOT SIT AT THE TOP. An attributed
secondary report is evidence; it is not a team or league declaration. Every
state carries `authority`, and `combine` lets an OFFICIAL source override a
SECONDARY one but never the reverse. Where they disagree the disagreement is
recorded rather than resolved silently.

WHAT COUNTS AS UNAVAILABLE, AND WHAT DELIBERATELY DOES NOT. Hard zero
eligibility belongs only to states that are actually terminal for the game:
OUT, injured reserve, PUP/NFI and equivalent inactive reserve, suspension,
and an official game-day inactive.

DOUBTFUL IS NOT ON THAT LIST AND THAT IS A CORRECTION. An earlier version of
this module hard-excluded Doubtful from the label alone. Doubtful is a
PROBABILISTIC availability state -- historically a minority of doubtful
players do play -- and turning a probability into a certainty because the
word sounds bad is exactly the fabrication this project forbids. Questionable
is the same. Neither moves a player out of the pool.

AND THE HONEST CONSEQUENCE IS A REFUSAL, NOT A NUMBER. The appearance model
carries no calibrated transition for Doubtful or Questionable at this
cutoff -- its two prediction-time feature groups are empty because no week-2
official row exists. So this module PRESERVES the designation, marks the
player's availability as NOT IDENTIFIED, and declines to supply a
coefficient. Forcing 0 or 1 would be inventing the very quantity that is
missing.

SELECTED BY THE CAPTURE'S OWN TIMESTAMP, NEVER BY FILE MTIME. Every blob in a
fresh checkout shares a clone mtime, so sorting on it picks an arbitrary
capture -- that mistake chose a 2026-09-11 file over the 2026-09-15 one and
nearly produced the conclusion that no post-week-1 evidence existed.
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

SPEC_VERSION = 'availability-feed-2'
SOURCE = 'espn_injuries_json'

#: This feed is an attributed secondary report. It is never the top authority.
AUTHORITY = 'SECONDARY_ATTRIBUTED_REPORT'
AUTHORITY_RANK = {'OFFICIAL_GAMEDAY_INACTIVE': 3,
                  'OFFICIAL_TEAM_OR_LEAGUE': 2,
                  'SECONDARY_ATTRIBUTED_REPORT': 1}

#: TERMINAL for this game. Hard zero eligibility is lawful here and nowhere
#: else on the label alone.
UNAVAILABLE_STATES = (
    'Out', 'Injured Reserve', 'Suspension',
    'Physically Unable to Perform', 'Non-Football Injury',
    'Non Football Injury', 'Practice Squad Injured Reserve',
)

#: PROBABILISTIC. Recorded, never acted on as a certainty. See the module
#: docstring for why Doubtful was removed from the terminal list.
PROBABILISTIC_STATES = ('Doubtful', 'Questionable', 'Day-To-Day', 'Day To Day')

AVAILABLE_STATES = ('Active',)

#: The five join outcomes the caller must be able to tell apart.
# THE FEED IS PAGE-CAPPED AT 25 PER CLUB AND DOES NOT SAY SO.
#
# Measured 2026-09-24 over the entire preserved capture history: 648 captures
# x 32 clubs = 20,736 club entries, and every single one carries EXACTLY 25
# injury items. Not one carries 24 or 26. A live injury census over 32 clubs
# and six weeks does not produce a one-valued distribution; a page size does.
#
# The response says `"status": "success"` and carries no pagination metadata
# at all -- no count, no pageIndex, no pageCount, no next. So a partial answer
# arrives wearing the word "success", which is this project's Class A defect.
#
# The cap is not even spent on injured players: across one capture's 800 items
# 585 (73%) are `Active`. A club's 25 slots held 16 Active, 4 Questionable, 4
# Injured Reserve and one Out. A genuinely OUT player ordered past the 25th is
# therefore invisible to us.
#
# This constant is NOT a tuning knob and nothing is inferred from it. It is
# recorded so that the condition is visible in the artifact rather than
# re-derived by whoever next wonders why a designation is missing.
_ESPN_PAGE_CAP = 25


def _truncation(doc) -> dict:
    """Is this capture cut off at the page cap?

    Reports what was counted, never an estimate of what was lost. How many
    players were dropped is not knowable from a truncated document and must
    not be guessed.
    """
    counts = {}
    for club in doc.get('injuries') or []:
        counts[str(club.get('displayName') or club.get('id'))] = len(
            club.get('injuries') or [])
    at_cap = [c for c, n in counts.items() if n == _ESPN_PAGE_CAP]
    return {
        'page_cap': _ESPN_PAGE_CAP,
        'n_clubs': len(counts),
        'n_clubs_at_cap': len(at_cap),
        'truncated': bool(counts) and len(at_cap) == len(counts),
        'per_club_counts': counts,
        'note': ('every club returned exactly the page cap, so this capture is '
                 'a truncated view and absence from it is doubly uninformative'
                 if counts and len(at_cap) == len(counts) else
                 'at least one club returned fewer than the cap, so the cap is '
                 'not binding everywhere in this capture'),
    }

JOIN_STATES = ('NO_ITEM', 'CURRENT_ITEM_MATCHED', 'CURRENT_ITEM_AFTER_CLOCK',
               'AMBIGUOUS', 'UNRESOLVED_IDENTITY')

_CACHE: dict = {}


def _ts(s):
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(str(s).replace('Z', '+00:00'))
    except (ValueError, AttributeError, TypeError):
        return None


def _classify(status: str) -> str:
    s = (status or '').strip()
    if s in UNAVAILABLE_STATES:
        return 'UNAVAILABLE'
    if s in AVAILABLE_STATES:
        return 'AVAILABLE'
    if s in PROBABILISTIC_STATES:
        return 'PROBABILISTIC'
    return 'UNRECOGNISED'


def newest_lawful(as_of) -> Outcome:
    """The newest capture whose OWN timestamp is at or before `as_of`.

    Also returns what was excluded BY THE CLOCK, so
    `CURRENT_ITEM_AFTER_CLOCK` is a measured state rather than an assumption.
    """
    cut = _ts(as_of)
    if cut is None:
        return Outcome.fail(
            'AVAILABILITY_NO_CLOCK',
            f'a feed cut is required and {as_of!r} does not parse. Taking the '
            f'newest capture on disk is how post-kickoff bytes enter a '
            f'pregame forecast.')
    key = ('newest', cut.isoformat())
    if key in _CACHE:
        return _CACHE[key]
    best, n, after = None, 0, []
    for f in sorted(_REPO.glob(f'nfl/vintage/{SOURCE}.*.json*')):
        try:
            d = json.loads(gzip.open(f, 'rt', errors='ignore').read()
                           if f.name.endswith('.gz') else f.read_text())
        except (OSError, ValueError):
            continue
        n += 1
        t = _ts(d.get('timestamp'))
        if t is None:
            continue
        if t > cut:
            after.append((t, f, d))
            continue
        if best is None or t > best[0]:
            best = (t, f, d)
    if best is None:
        return Outcome.blocked(
            'AVAILABILITY_NO_LAWFUL_CAPTURE',
            f'{n} {SOURCE} capture(s) exist and none is stamped at or before '
            f'{cut.isoformat()}; {len(after)} are later. An empty feed is a '
            f'refusal, not an empty injury list.',
            cause=Cause.DATA, n_captures=n, n_after_cut=len(after))
    t, f, d = best

    def flatten(doc, stamp, blob):
        out = []
        for club in doc.get('injuries') or []:
            for it in club.get('injuries') or []:
                a = it.get('athlete') or {}
                out.append({
                    'club': club.get('displayName'),
                    'name': a.get('displayName'),
                    'position': (a.get('position') or {}).get('abbreviation'),
                    # THE ORIGINAL TEXT IS KEPT VERBATIM. A normalised label
                    # is a lossy summary and the reader may need the wording.
                    'designation_text': (it.get('status') or '').strip(),
                    'published_at': it.get('date'),
                    'retrieved_at': stamp,
                    'source': SOURCE, 'blob': blob,
                    'authority': AUTHORITY,
                    'detail': (it.get('shortComment') or '')[:240]})
        return out

    items = flatten(d, t.isoformat(), str(f.relative_to(_REPO)))
    # Items from captures later than the cut, kept ONLY so a caller can say
    # "this exists and is after the clock" instead of "this does not exist".
    later_names = set()
    for t2, f2, d2 in after:
        for it in flatten(d2, t2.isoformat(), str(f2.relative_to(_REPO))):
            if it['name']:
                later_names.add(it['name'])
    out = Outcome.ok(
        'AVAILABILITY_FEED_SELECTED',
        value={'items': items, 'timestamp': t.isoformat(),
               'blob': str(f.relative_to(_REPO)),
               'truncation': _truncation(d),
               'names_only_after_clock': sorted(
                   later_names - {i['name'] for i in items if i['name']})},
        spec_version=SPEC_VERSION, source=SOURCE, authority=AUTHORITY,
        capture_timestamp=t.isoformat(), blob=str(f.relative_to(_REPO)),
        feed_truncated=_truncation(d)['truncated'],
        n_items=len(items), n_captures_scanned=n,
        n_captures_after_cut=len(after),
        selection_rule='the newest capture whose OWN timestamp field is at or '
                       'before the cut; file mtime is never consulted',
        as_of=cut.isoformat())
    _CACHE[key] = out
    return out


def states(as_of, names_by_id: dict) -> Outcome:
    """gsis_id -> availability evidence, with the join outcome named.

    THE JOIN IS ON DISPLAY NAME AND THAT IS A STATED WEAKNESS. The feed
    carries no gsis_id. The caller supplies the id -> name map it already
    trusts, a name resolving to more than one id is AMBIGUOUS and refused,
    and an id with no name at all is UNRESOLVED_IDENTITY. Neither is quietly
    turned into "no news".
    """
    sel = newest_lawful(as_of)
    if not sel.ok:
        return sel
    items = sel.value['items']
    truncated = bool((sel.value.get('truncation') or {}).get('truncated'))
    after_only = set(sel.value['names_only_after_clock'])
    by_name = {}
    for it in items:
        if it['name']:
            by_name.setdefault(it['name'], []).append(it)
    for v in by_name.values():
        v.sort(key=lambda x: str(x['published_at']), reverse=True)

    rev = {}
    for g, nm in (names_by_id or {}).items():
        rev.setdefault(nm, []).append(g)

    out, counts = {}, dict.fromkeys(JOIN_STATES, 0)
    for nm, ids in rev.items():
        for g in ids:
            if not nm:
                out[g] = {'join_state': 'UNRESOLVED_IDENTITY',
                          'availability': 'NOT_IDENTIFIED',
                          'reason': 'this id carries no display name, so the '
                                    'name-keyed feed cannot be consulted for '
                                    'him at all'}
                counts['UNRESOLVED_IDENTITY'] += 1
                continue
            if len(ids) > 1:
                out[g] = {'join_state': 'AMBIGUOUS',
                          'availability': 'NOT_IDENTIFIED',
                          'candidates': sorted(ids),
                          'reason': f'{nm!r} resolves to {len(ids)} ids; '
                                    f'refused rather than assigned'}
                counts['AMBIGUOUS'] += 1
                continue
            it = (by_name.get(nm) or [None])[0]
            if it is None:
                js = ('CURRENT_ITEM_AFTER_CLOCK' if nm in after_only
                      else 'NO_ITEM')
                counts[js] += 1
                out[g] = {
                    'join_state': js,
                    'availability': 'NOT_IDENTIFIED',
                    'reason': (
                        'an item for this player exists only in a capture '
                        'LATER than the forecast cut; using it would be '
                        'leakage' if js == 'CURRENT_ITEM_AFTER_CLOCK' else
                        'no item for this player in the newest lawful '
                        'capture. ABSENCE FROM AN INJURY FEED IS NOT '
                        'EVIDENCE OF HEALTH.'
                        + (' This capture is TRUNCATED at the feed\'s page '
                           'cap of %d per club, so his absence may mean only '
                           'that the list was cut before reaching him. It is '
                           'not evidence that the feed had nothing to say '
                           'about him.' % _ESPN_PAGE_CAP
                           if truncated else ''))}
                continue
            counts['CURRENT_ITEM_MATCHED'] += 1
            cls = _classify(it['designation_text'])
            out[g] = {
                'join_state': 'CURRENT_ITEM_MATCHED',
                'availability': cls,
                'designation_text': it['designation_text'],
                'published_at': it['published_at'],
                'retrieved_at': it['retrieved_at'],
                'source': it['source'], 'blob': it['blob'],
                'authority': it['authority'],
                'detail': it['detail'],
                'acts_on_eligibility': cls == 'UNAVAILABLE',
                'reason': (
                    'a terminal designation for this game' if cls == 'UNAVAILABLE'
                    else 'an active designation' if cls == 'AVAILABLE'
                    else 'a PROBABILISTIC designation. It is preserved and it '
                         'does NOT move him out of the pool. No calibrated '
                         'transition for this state exists at this cutoff, so '
                         'this module declines to supply one rather than '
                         'forcing 0 or 1'
                    if cls == 'PROBABILISTIC'
                    else 'a designation this module does not recognise; '
                         'recorded and not acted on')}
    return Outcome.ok(
        'AVAILABILITY_STATES', value=out, spec_version=SPEC_VERSION,
        source=SOURCE, authority=AUTHORITY,
        capture_timestamp=sel.value['timestamp'], blob=sel.value['blob'],
        n_ids=len(out), join_state_counts=counts,
        n_unavailable=sum(1 for v in out.values()
                          if v.get('availability') == 'UNAVAILABLE'),
        n_probabilistic=sum(1 for v in out.values()
                            if v.get('availability') == 'PROBABILISTIC'),
        probabilistic_players=sorted(
            names_by_id.get(g) for g, v in out.items()
            if v.get('availability') == 'PROBABILISTIC'),
        probabilistic_handling=(
            'PRESERVED AND NOT ACTED ON. Doubtful and Questionable are '
            'probabilistic availability states. No lawful calibrated '
            'transition exists for them at this cutoff, so the evidence is '
            'kept and no coefficient is fabricated.'),
        evidence_is='ATTRIBUTED_SECONDARY_REPORT_NOT_AN_OFFICIAL_DECLARATION')


def combine(secondary: dict, official: dict | None = None) -> Outcome:
    """Official evidence outranks this feed; this feed never outranks it.

    `official` is {gsis_id: {'availability':..., 'authority':...}} from a team
    or league declaration or a game-day inactive list. Where both speak the
    official answer wins and the disagreement is recorded; where only the
    secondary speaks it is used and labelled as secondary.
    """
    out, disagree = {}, []
    for g, sec in (secondary or {}).items():
        off = (official or {}).get(g)
        if not off:
            out[g] = dict(sec)
            continue
        a_off = AUTHORITY_RANK.get(off.get('authority'), 2)
        a_sec = AUTHORITY_RANK.get(sec.get('authority'), 1)
        win = off if a_off >= a_sec else sec
        if off.get('availability') != sec.get('availability'):
            disagree.append({
                'gsis_id': g, 'official': off.get('availability'),
                'secondary': sec.get('availability'),
                'resolved_to': win.get('availability'),
                'rule': 'the higher authority wins; the disagreement is '
                        'recorded rather than resolved silently'})
        out[g] = {**sec, **win, 'had_official_override': a_off >= a_sec}
    for g, off in (official or {}).items():
        out.setdefault(g, dict(off))
    return Outcome.ok(
        'AVAILABILITY_COMBINED', value=out, spec_version=SPEC_VERSION,
        n_ids=len(out), n_disagreements=len(disagree),
        disagreements=disagree,
        rule='OFFICIAL_GAMEDAY_INACTIVE > OFFICIAL_TEAM_OR_LEAGUE > '
             'SECONDARY_ATTRIBUTED_REPORT')
