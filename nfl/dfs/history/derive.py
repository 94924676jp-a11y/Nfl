"""Ownership and duplication, derived from a field we hold.

TWO NUMBERS THAT ARE NOT THE SAME NUMBER

The operator publishes a `% Drafted` per athlete. We can also count it
ourselves from the entrant lineups. Those are kept APART -- operator
ownership, derived ownership, and the difference between them -- because
where they disagree the disagreement is the finding, and a single merged
column would hide it. Neither is corrected toward the other.

DERIVED OWNERSHIP MAY NOT CLAIM A COMPLETENESS IT CANNOT PROVE

    ownership = entries containing the athlete / valid field entries

That denominator is only the field if the entries we hold ARE the field. A
partial download gives a perfectly well-formed number that is wrong, and it
is wrong in the direction nobody checks. So every derived observation
carries its denominator and the completeness state of the field it came
from, and a field whose completeness is not established is never labelled
COMPLETE.

DUPLICATION IS POSITION-SENSITIVE WHERE THE CONTEST IS

In Classic, two entries with the same nine players are the same lineup
however the slots are ordered. In Showdown they are NOT: a captain is scored
at 1.5x, so CPT Mahomes + FLEX Kelce and CPT Kelce + FLEX Mahomes are
different lineups with different scores. The canonical form therefore keeps
the captain slot distinguished and sorts only within the interchangeable
ones.
"""
from __future__ import annotations

import collections
import hashlib
import pathlib
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.dfs.history import contracts as C                           # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome         # noqa: E402

SPEC_VERSION = 'nfl-dfs-derivation-0'

#: Slots whose identity changes the lineup's score, so they may not be
#: sorted away. DraftKings scores a Showdown captain at 1.5x.
DISTINGUISHED_SLOTS = ('CPT',)


def canonical_roster(entry: C.ContestEntry) -> Optional[Tuple[str, ...]]:
    """A lineup reduced to what makes it the same lineup as another.

    Returns None when the lineup did not parse -- an unparsed lineup is not
    a lineup with no players, and counting it as one would invent a
    duplicate group of entries that have nothing in common.
    """
    if not entry.lineup_slots:
        return None
    distinguished = [f'{slot}:{name}' for slot, name in entry.lineup_slots
                     if slot in DISTINGUISHED_SLOTS]
    interchangeable = sorted(name for slot, name in entry.lineup_slots
                             if slot not in DISTINGUISHED_SLOTS)
    return tuple(sorted(distinguished) + interchangeable)


def lineup_hash(roster: Sequence[str]) -> str:
    return 'LU-' + hashlib.sha256(
        '|'.join(roster).encode()).hexdigest()[:16]


def duplication(entries: Sequence[C.ContestEntry]) -> Outcome:
    """How many entrants submitted the same lineup."""
    parsed = [e for e in entries if e.lineup_slots]
    if not parsed:
        return Outcome.blocked(
            'NO_PARSED_LINEUP',
            f'none of {len(entries)} entry row(s) carries a lineup this '
            f'parser could read, so duplication cannot be counted. Zero '
            f'duplicates would be a false clean result.', cause=Cause.DATA)
    groups: Dict[Tuple[str, ...], List[str]] = collections.defaultdict(list)
    for e in parsed:
        groups[canonical_roster(e)].append(e.entry_id or '')
    n = len(parsed)
    rows = [{'lineup_hash': lineup_hash(r),
             'canonical_roster': list(r),
             'duplicate_count': len(ids),
             'fraction_of_field': len(ids) / n,
             'entry_ids': sorted(x for x in ids if x)[:50]}
            for r, ids in groups.items()]
    rows.sort(key=lambda x: (-x['duplicate_count'], x['lineup_hash']))
    return Outcome.ok(
        'DUPLICATION_DERIVED',
        {'lineups': rows,
         'n_entries_parsed': n,
         'n_entries_supplied': len(entries),
         'n_entries_unparsed': len(entries) - n,
         'n_distinct_lineups': len(rows),
         'max_duplicate_count': rows[0]['duplicate_count'],
         'n_unique_lineups': sum(1 for r in rows
                                 if r['duplicate_count'] == 1),
         'derivation_version': SPEC_VERSION,
         'distinguished_slots': list(DISTINGUISHED_SLOTS),
         'denominator_note':
             'fraction_of_field is over the PARSED entries, not over the '
             'contest\'s declared field size. Where those differ the field '
             'we hold is not the field.'},
        detail=f'{len(rows)} distinct lineup(s) over {n} parsed entry(ies); '
               f'largest duplicate group {rows[0]["duplicate_count"]}')


def derived_ownership(entries: Sequence[C.ContestEntry], *,
                      contest_key: str, observed_at: str,
                      observation_type: str = C.SNAPSHOT_UNKNOWN,
                      completeness: str = C.COMPLETENESS_UNKNOWN,
                      raw_sha256: str = None) -> Outcome:
    """Count ownership from the field, and say what the denominator was."""
    parsed = [e for e in entries if e.lineup_slots]
    if not parsed:
        return Outcome.blocked(
            'NO_PARSED_LINEUP',
            f'none of {len(entries)} entry row(s) carries a readable '
            f'lineup, so ownership cannot be counted from the field.',
            cause=Cause.DATA)
    n = len(parsed)
    seen: Dict[str, int] = collections.Counter()
    for e in parsed:
        # an athlete rostered twice in one entry is still one entry
        for name in {nm for _slot, nm in e.lineup_slots}:
            seen[name] += 1
    obs = [C.OwnershipObservation(
        contest_key=contest_key, athlete_name=name, observed_at=observed_at,
        observation_type=observation_type,
        ownership=count / n, source=C.DERIVED_FROM_FIELD, denominator=n,
        derivation_version=SPEC_VERSION, completeness=completeness,
        raw_sha256=raw_sha256)
        for name, count in sorted(seen.items())]
    return Outcome.ok(
        'OWNERSHIP_DERIVED',
        {'observations': obs, 'n_athletes': len(obs), 'denominator': n,
         'n_entries_supplied': len(entries),
         'n_entries_unparsed': len(entries) - n,
         'completeness': completeness,
         'derivation_version': SPEC_VERSION,
         'completeness_note':
             'the denominator is the entries THIS ARTIFACT holds. It is the '
             'field only where completeness is COMPLETE; under any other '
             'state these are shares of what we have, not of the contest.'},
        detail=f'{len(obs)} athlete(s) over {n} parsed entry(ies), '
               f'completeness {completeness}')


def operator_ownership(athletes: Sequence[C.ContestAthleteSummary], *,
                       contest_key: str, observed_at: str,
                       observation_type: str = C.SNAPSHOT_UNKNOWN,
                       raw_sha256: str = None) -> Outcome:
    """The operator's own `% Drafted`, carried as observations, not merged."""
    have = [a for a in athletes if a.percent_drafted is not None]
    if not have:
        return Outcome.not_applicable(
            'NO_OPERATOR_OWNERSHIP_IN_FILE',
            f'{len(athletes)} athlete summary row(s) and none carries a '
            f'percent-drafted column. Recorded rather than left silent: the '
            f'absence of the operator number is itself a fact about this '
            f'artifact.')
    obs = [C.OwnershipObservation(
        contest_key=contest_key, athlete_name=a.athlete_name,
        observed_at=observed_at, observation_type=observation_type,
        # DK publishes a PERCENT; observations are stored as fractions.
        ownership=a.percent_drafted / 100.0,
        source=C.OPERATOR_PUBLISHED, denominator=None,
        roster_position=a.roster_position, athlete_id=a.athlete_id,
        fantasy_points=a.fantasy_points, raw_sha256=raw_sha256)
        for a in sorted(have, key=lambda x: x.athlete_name)]
    return Outcome.ok(
        'OPERATOR_OWNERSHIP_READ',
        {'observations': obs, 'n_athletes': len(obs),
         'units': 'stored as a FRACTION; the file publishes a percent'},
        detail=f'{len(obs)} athlete(s) with an operator-published share')


def compare_ownership(operator: Sequence[C.OwnershipObservation],
                      derived: Sequence[C.OwnershipObservation]) -> Outcome:
    """Operator versus derived, per athlete. Neither is corrected."""
    o = {x.athlete_name: x for x in operator}
    d = {x.athlete_name: x for x in derived}
    rows = []
    for name in sorted(set(o) | set(d)):
        a, b = o.get(name), d.get(name)
        rows.append({
            'athlete_name': name,
            'operator': None if a is None else a.ownership,
            'derived': None if b is None else b.ownership,
            'difference': (None if a is None or b is None
                           else b.ownership - a.ownership),
            'denominator': None if b is None else b.denominator,
            'in_operator_table': a is not None,
            'in_derived_field': b is not None,
        })
    both = [r for r in rows if r['difference'] is not None]
    worst = max(both, key=lambda r: abs(r['difference'])) if both else None
    return Outcome.ok(
        'OWNERSHIP_COMPARED',
        {'rows': rows, 'n_athletes': len(rows), 'n_comparable': len(both),
         'n_operator_only': sum(1 for r in rows
                                if r['in_operator_table']
                                and not r['in_derived_field']),
         'n_derived_only': sum(1 for r in rows
                               if r['in_derived_field']
                               and not r['in_operator_table']),
         'max_abs_difference': (None if worst is None
                                else abs(worst['difference'])),
         'largest_disagreement': worst,
         'note': 'neither number is adjusted toward the other. A large '
                 'difference is evidence about the field we hold -- most '
                 'often that it is not complete -- and merging the two '
                 'columns would destroy exactly that evidence.'},
        detail=f'{len(both)} athlete(s) comparable of {len(rows)}; '
               f'largest difference '
               f'{"n/a" if worst is None else round(abs(worst["difference"]), 6)}')
