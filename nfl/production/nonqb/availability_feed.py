"""The secondary availability feed, graded — not a model coefficient.

WHAT WAS WRONG. The appearance mechanism consumes one source: the nflverse
`injuries` CSV captures. Every one of those for 2026 carries WEEK 1 ONLY --
769 rows across eight blobs, zero for week 2 -- so `n_with_an_injuries_row`
is 0 for every player on a week-2 board and two of the model's five feature
groups contribute nothing.

Meanwhile 428 ESPN injury captures sit in the same vintage directory. The
newest one lawful at a 2026-09-16 cutoff is stamped 2026-09-15T13:06Z, after
week 1 was played, and it carries current availability state: Detroit's
Monday walkthrough participation, Isiah Pacheco's Monday surgery, and Buffalo
listing Ty Johnson OUT with a hamstring. The board gave Johnson 4.1 carries.

Two transformations stopped it, and both had to be found:

  1. `readiness.lawful_injuries_rows` selects `lawful_paths('injuries', ...)`.
     The ESPN feed is a different source name, so it was never offered.
  2. `appearance_model.parse_injuries_rows` requires an integer season AND
     week on every row. The ESPN schema carries neither -- it is a
     current-state feed with a per-item date -- so every row would have been
     dropped by a bare `continue` even if it had been offered.

WHY THIS IS AN ELIGIBILITY INPUT AND NOT A FEATURE. The obvious move is to
map ESPN's status vocabulary onto the `report_status` the logistic was
trained on and feed it in. That is a modelling decision with a fitted
consequence and no evidence behind the mapping, and it would change a frozen
mechanism's inputs on a guess. What needs no coefficient at all is the thing
the board actually got wrong: a player the league has declared OUT is not in
the opportunity pool. That is the same discipline `participant_class` already
applies to practice-squad and reserve membership, so this feeds THAT, and the
appearance logistic is left alone.

SELECTED BY THE CAPTURE'S OWN TIMESTAMP, NEVER BY FILE MTIME. Every blob in a
fresh checkout shares a mtime from the clone, so sorting on it picks an
arbitrary capture -- that mistake chose the 2026-09-11 file over the
2026-09-15 one and nearly produced the conclusion that no post-week-1
evidence existed.

IT IS EVIDENCE, NOT A DECLARATION. Every row carries its capture, its item
date and its source, and the state it implies is separate from the roster
class it is combined with. Where the two disagree the disagreement is
recorded rather than resolved silently.
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

SPEC_VERSION = 'availability-feed-espn-1'
SOURCE = 'espn_injuries_json'

#: ESPN's status vocabulary -> what it says about GAME AVAILABILITY.
#: Only two verdicts are acted on. Everything else is INFORMATION: it is
#: recorded, it is reported, and it does not move a player out of the pool,
#: because "Questionable" is a genuine uncertainty and resolving it in either
#: direction would be inventing a transition probability nobody measured.
DECLARED_UNAVAILABLE = ('Out', 'Injured Reserve', 'Suspension',
                        'Physically Unable to Perform', 'Doubtful')
DECLARED_AVAILABLE = ('Active',)

_CACHE: dict = {}


def _ts(s):
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(str(s).replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        return None


def newest_lawful(as_of) -> Outcome:
    """The newest ESPN capture whose OWN timestamp is at or before `as_of`."""
    cut = _ts(as_of)
    if cut is None:
        return Outcome.fail(
            'AVAILABILITY_NO_CLOCK',
            f'a feed cut is required and {as_of!r} does not parse. Selecting '
            f'the newest capture on disk is how post-kickoff bytes enter a '
            f'pregame forecast.')
    key = ('newest', cut.isoformat())
    if key in _CACHE:
        return _CACHE[key]
    best, n, n_after = None, 0, 0
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
            n_after += 1
            continue
        if best is None or t > best[0]:
            best = (t, f, d)
    if best is None:
        return Outcome.blocked(
            'AVAILABILITY_NO_LAWFUL_CAPTURE',
            f'{n} {SOURCE} capture(s) exist and none is stamped at or before '
            f'{cut.isoformat()}. {n_after} are later. An empty feed is a '
            f'refusal, not an empty injury list.',
            cause=Cause.DATA, n_captures=n, n_after_cut=n_after)
    t, f, d = best
    items = []
    for club in d.get('injuries') or []:
        for it in club.get('injuries') or []:
            a = it.get('athlete') or {}
            items.append({
                'club': club.get('displayName'),
                'name': a.get('displayName'),
                'position': (a.get('position') or {}).get('abbreviation'),
                'status': (it.get('status') or '').strip(),
                'item_date': it.get('date'),
                'detail': (it.get('shortComment') or '')[:240]})
    out = Outcome.ok(
        'AVAILABILITY_FEED_SELECTED',
        value={'items': items, 'timestamp': t.isoformat(),
               'blob': str(f.relative_to(_REPO))},
        spec_version=SPEC_VERSION, source=SOURCE,
        capture_timestamp=t.isoformat(), blob=str(f.relative_to(_REPO)),
        n_items=len(items), n_captures_scanned=n,
        n_captures_after_cut=n_after,
        selection_rule="the newest capture whose OWN timestamp field is at or "
                       "before the cut; file mtime is never consulted",
        as_of=cut.isoformat())
    _CACHE[key] = out
    return out


def states(as_of, names_by_id: dict) -> Outcome:
    """gsis_id -> declared availability, for the ids we can name.

    THE JOIN IS ON DISPLAY NAME AND THAT IS A WEAKNESS, STATED HERE. The ESPN
    feed carries no gsis_id. The caller supplies the id -> name map it already
    trusts (the same resolver the board prints from), and a name matching more
    than one id is REFUSED rather than assigned. Where a player is absent from
    the feed the answer is NO_ITEM -- which in an injury feed means no injury
    news, and is NOT the same as a positive declaration of health.
    """
    sel = newest_lawful(as_of)
    if not sel.ok:
        return sel
    items = sel.value['items']
    by_name = {}
    for it in items:
        if it['name']:
            by_name.setdefault(it['name'], []).append(it)
    # Newest item per name, by its own date.
    for k, v in by_name.items():
        v.sort(key=lambda x: str(x['item_date']), reverse=True)

    rev = {}
    for g, nm in (names_by_id or {}).items():
        if nm:
            rev.setdefault(nm, []).append(g)
    out, ambiguous, matched = {}, {}, 0
    for nm, ids in rev.items():
        it = (by_name.get(nm) or [None])[0]
        if len(ids) > 1:
            ambiguous[nm] = sorted(ids)
            continue
        g = ids[0]
        if it is None:
            out[g] = {'declared': 'NO_ITEM', 'status': None,
                      'item_date': None, 'detail': None,
                      'means': 'no injury news for this player in the newest '
                               'lawful capture. NOT a declaration of health.'}
            continue
        matched += 1
        st = it['status']
        declared = ('UNAVAILABLE' if st in DECLARED_UNAVAILABLE else
                    'AVAILABLE' if st in DECLARED_AVAILABLE else 'UNCERTAIN')
        out[g] = {'declared': declared, 'status': st,
                  'item_date': it['item_date'], 'detail': it['detail'],
                  'means': ('the feed declares him out of this game'
                            if declared == 'UNAVAILABLE' else
                            'the feed carries a non-committal designation; it '
                            'is recorded and does NOT move him out of the '
                            'pool, because resolving an uncertainty in either '
                            'direction invents a transition probability'
                            if declared == 'UNCERTAIN' else
                            'the feed carries an active designation')}
    return Outcome.ok(
        'AVAILABILITY_STATES', value=out, spec_version=SPEC_VERSION,
        source=SOURCE, capture_timestamp=sel.value['timestamp'],
        blob=sel.value['blob'], n_ids=len(out), n_matched_an_item=matched,
        n_no_item=sum(1 for v in out.values()
                      if v['declared'] == 'NO_ITEM'),
        n_unavailable=sum(1 for v in out.values()
                          if v['declared'] == 'UNAVAILABLE'),
        n_uncertain=sum(1 for v in out.values()
                        if v['declared'] == 'UNCERTAIN'),
        ambiguous_names_refused=ambiguous,
        evidence_is='INFORMATION_INPUT_ATTRIBUTED_NOT_AN_OFFICIAL_DECLARATION')
