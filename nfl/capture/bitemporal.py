"""Bitemporal assertions for the data plane. P7 Part B.

WHAT A BITEMPORAL FACT IS, AND WHY ONE CLOCK IS NOT ENOUGH

Every stored fact in this repository has two independent time axes and the
project has been storing only one of them consistently:

    VALID TIME        when the fact was true of the world
    TRANSACTION TIME  when WE learned it

`retrieved_at` is transaction time. `effective_scope.valid_from` is an attempt
at valid time. They answer different questions and neither substitutes for the
other:

  * A depth chart stamped `dt = 2026-09-14` is VALID from 2026-09-14. That
    says nothing about when we could read it.
  * The `injuries` mirror first carried `report_status = 'Out'` for two New
    England players in the capture RETRIEVED at 2026-09-10T05:05:18Z. The
    designation was VALID before the 2026-09-10T00:20Z kickoff of NE@SEA -- the
    league filed it on the Friday -- and we LEARNED it 4h45m AFTER that game had
    started. Valid time says the fact was pre-kickoff. Transaction time says we
    did not have it. A forecast may only read the second.

MEASURED, 2026-09-15, over the seven distinct `injuries` content vintages on
disk and the `schedules` blob `bfb4ca5952e3a974`:

    week-1 player rows tracked                                        182
    rows whose first observation postdates their own kickoff            0
    rows whose report/practice status CHANGED after their own kickoff   5
        NE 00-0037413, NE 00-0040734, SEA 00-0038765,
        SEA 00-0040648, SEA 00-0040733

So the feed IS revised across a kickoff. Enforcement on transaction time is
load-bearing here, not ceremonial.

THE RULE THIS MODULE ENFORCES

    A forecast cut at `as_of` may read a fact only when that fact's LEARNED
    time is strictly earlier than `as_of`. Valid time never licenses a read.

THE GRANULARITY TRAP, WHICH IS THE REASON THIS IS A MODULE AND NOT AN `if`

`nfl/production/nonqb/qb_allocation.py:473-484` already guards its depth chart.
It compares `str(got) >= str(bound)` where `got` is the maximum `dt` in the
file -- a DATE, `'2026-09-14'` -- and `bound` is an ISO instant,
`'2026-09-13T17:00:00+00:00'`. Compared as strings, `'2026-09-13'` sorts BEFORE
`'2026-09-13T17:00:00+00:00'`, because the shorter string is a prefix. A depth
chart published at 23:00 on a Sunday therefore passes a guard protecting a
13:00 kickoff that same Sunday.

`vintage_selector.FAMILIES['depth_charts']['ceiling']` already says the `dt` is
a daily stamp and that intra-day ordering is not recoverable from it. The guard
does not honour its own ceiling. So a DATE-granularity learned time is lawful
here only when the WHOLE DAY closes before the cut, and otherwise refuses by
name rather than resolving the ambiguity in the reader's favour.

WHAT THIS MODULE DOES NOT DO

It authorises nothing. `readable_at` returning PASS is a statement about two
clocks and is not permission to consume a source; that decision lives with the
owner and with `nfl/capture/availability.eligibility_record`, which keeps
`ordering_ok` and `authorized` deliberately unmerged for the same reason.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import enum
import json
import pathlib
import sys
from typing import Optional

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402

SPEC_VERSION = 'bitemporal-1'


class Granularity(str, enum.Enum):
    """How precisely a clock is known. Never widened to make a read lawful."""
    INSTANT = 'INSTANT'    # a real timestamp, sub-second
    DATE = 'DATE'          # a calendar day only; intra-day order unrecoverable
    UNKNOWN = 'UNKNOWN'    # no clock at all


class BitemporalError(RuntimeError):
    """A fact that cannot be placed on both axes. A defect, never a nuance."""


def parse(t) -> Optional[dt.datetime]:
    """ISO-8601 -> aware UTC datetime, or None. Never a string comparison.

    Deliberately the same rule as `vintage_selector.parse_ts`: two parsers with
    two rules is how `'2026-09-10T16:00:00+00:00'` and `'2026-09-10T16:00:00Z'`
    came to order differently in the same repository.
    """
    if t is None or t == '':
        return None
    if isinstance(t, dt.datetime):
        return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
    if isinstance(t, dt.date):
        return dt.datetime(t.year, t.month, t.day, tzinfo=dt.timezone.utc)
    try:
        d = dt.datetime.fromisoformat(str(t).strip().replace('Z', '+00:00'))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def granularity_of(t) -> Granularity:
    """What the WRITTEN FORM of this clock actually resolves.

    A bare `'2026-09-14'` resolves a day. Reading it as midnight is an
    invention: the depth chart carrying it may have been published at any hour
    of that day, and `nflverse` does not say which.
    """
    if t is None or t == '':
        return Granularity.UNKNOWN
    if isinstance(t, dt.datetime):
        return Granularity.INSTANT
    if isinstance(t, dt.date):
        return Granularity.DATE
    s = str(t).strip()
    if parse(s) is None:
        return Granularity.UNKNOWN
    return Granularity.INSTANT if ('T' in s or ' ' in s) else Granularity.DATE


@dataclasses.dataclass(frozen=True)
class Fact:
    """One stored fact on both time axes, with the authority of each clock.

    `learned_at_authority` is not decoration. E3 in WS12 measured that for
    `official_inactives` and `official_injury_report` the "source-provided"
    publication instant IS the HTTP `Date` header of our own request, with a
    lag of exactly 0.000 hours in 188 of 188 rows. A `published_at` that is
    really a retrieval time must say so where a consumer will see it.
    """
    subject: str                       # what the fact is about
    source: str                        # the registry source name
    learned_at: Optional[str]          # TRANSACTION TIME
    learned_at_authority: str = 'UNDECLARED'
    valid_from: Optional[str] = None   # VALID TIME, open below
    valid_to: Optional[str] = None     # VALID TIME, open above
    valid_authority: str = 'UNDECLARED'
    content_sha256: Optional[str] = None
    blob: Optional[str] = None
    note: str = ''

    @property
    def learned_granularity(self) -> Granularity:
        return granularity_of(self.learned_at)

    def record(self) -> dict:
        d = dataclasses.asdict(self)
        d['spec_version'] = SPEC_VERSION
        d['learned_granularity'] = self.learned_granularity.value
        return d


# ------------------------------------------------------------------ axis 1
def assert_bitemporal(fact: Fact) -> Outcome:
    """Both axes present and orderable, or a NAMED refusal.

    Three refusals, and they are different failures needing different repairs:

      NO_TRANSACTION_TIME  we cannot say when we learned it. Nothing may read
                           it under any cut. A capture defect.
      LEARNED_BEFORE_VALID we recorded learning a fact before it became true.
                           For an OBSERVED fact that is impossible, so one of
                           the two clocks is mislabelled. A schema defect.
      NO_VALID_TIME        DEFERRED, not FAIL. Plenty of real captures have no
                           per-row effective clock -- the 2025+ `injuries`
                           schema dropped `date_modified` -- and that is a
                           documented ceiling, not a broken record. It bars
                           valid-time reasoning, and bars nothing else.
    """
    got = parse(fact.learned_at)
    if got is None:
        return Outcome.fail(
            'NO_TRANSACTION_TIME',
            f'{fact.source}/{fact.subject}: learned_at is '
            f'{fact.learned_at!r}, which places the fact on no cut at all. A '
            f'fact we cannot date the learning of is unreadable by every '
            f'forecast, not readable by all of them.',
            source=fact.source, subject=fact.subject)
    vf = parse(fact.valid_from)
    if vf is not None and got < vf:
        return Outcome.fail(
            'LEARNED_BEFORE_VALID',
            f'{fact.source}/{fact.subject}: learned_at {got.isoformat()} '
            f'precedes valid_from {vf.isoformat()}. We cannot have observed a '
            f'fact before it was true, so one of these two clocks is carrying '
            f'the other one\'s meaning. Recorded authorities are '
            f'learned={fact.learned_at_authority!r}, '
            f'valid={fact.valid_authority!r}.',
            source=fact.source, subject=fact.subject,
            learned_at=got.isoformat(), valid_from=vf.isoformat())
    if vf is None:
        return Outcome.deferred(
            'NO_VALID_TIME',
            f'{fact.source}/{fact.subject}: transaction time is recorded and '
            f'usable, and the fact carries no valid_from. Valid-time '
            f'reasoning is unavailable for it; cut enforcement is not.',
            owed=f'{fact.source}:valid_from', source=fact.source,
            learned_at=got.isoformat(),
            learned_granularity=fact.learned_granularity.value)
    return Outcome.ok(
        'BITEMPORAL_OK', value=fact,
        detail=f'{fact.source}/{fact.subject}: learned {got.isoformat()} '
               f'({fact.learned_granularity.value}), valid from '
               f'{vf.isoformat()}',
        source=fact.source, learned_at=got.isoformat(),
        valid_from=vf.isoformat(),
        learned_granularity=fact.learned_granularity.value)


# ------------------------------------------------------------------ axis 2
def readable_at(fact: Fact, cut) -> Outcome:
    """May a forecast cut at `cut` read this fact? Transaction time only.

    THE ONE RULE: `learned_at < cut`, strictly, on parsed instants.

    A DATE-granularity learned time is lawful only when the whole day closes at
    or before the cut. Anything else is refused as TOO_COARSE rather than
    resolved in the reader's favour -- that resolution is what lets a depth
    chart stamped with a game day pass a guard for a kickoff earlier that day.

    `cut` is required and there is no default. A missing cut refuses, for the
    reason `vintage_selector.resolve_as_of` gives: "now" admits post-kickoff
    facts and "no bound" admits every fact ever recorded.
    """
    c = parse(cut)
    if c is None:
        return Outcome.blocked(
            'BITEMPORAL_CUT_UNRESOLVED',
            f'{fact.source}/{fact.subject}: readable_at was called with cut='
            f'{cut!r}. No cut is not any cut, and it is not an open one.',
            cause=Cause.GOVERNANCE, source=fact.source)
    base = assert_bitemporal(fact)
    if base.state is State.FAIL:
        return base
    got = parse(fact.learned_at)
    gran = fact.learned_granularity
    if gran is Granularity.DATE:
        day_end = got + dt.timedelta(days=1)
        if day_end <= c:
            return Outcome.ok(
                'READABLE_AT_CUT', value=True,
                detail=f'{fact.source}/{fact.subject}: learned on '
                       f'{got.date().isoformat()}, a day that closed at '
                       f'{day_end.isoformat()}, at or before the cut '
                       f'{c.isoformat()}',
                source=fact.source, cut=c.isoformat(),
                learned_granularity=gran.value,
                bound_used='end of the learned DAY')
        return Outcome.blocked(
            'LEARNED_TIME_GRANULARITY_TOO_COARSE',
            f'{fact.source}/{fact.subject}: learned_at is the calendar day '
            f'{got.date().isoformat()}, which does not close until '
            f'{day_end.isoformat()} -- after the cut {c.isoformat()}. The '
            f'fact may have been published at any hour of that day, including '
            f'after the cut, and the source does not record which. Refusing '
            f'rather than reading the day as midnight: reading it as midnight '
            f'is what lets a chart published on a Sunday evening certify a '
            f'Sunday afternoon kickoff.',
            cause=Cause.DATA, source=fact.source, cut=c.isoformat(),
            learned_at=fact.learned_at, learned_granularity=gran.value)
    if got < c:
        return Outcome.ok(
            'READABLE_AT_CUT', value=True,
            detail=f'{fact.source}/{fact.subject}: learned {got.isoformat()} '
                   f'< cut {c.isoformat()}',
            source=fact.source, cut=c.isoformat(),
            learned_at=got.isoformat(), learned_granularity=gran.value,
            bound_used='the learned INSTANT')
    return Outcome.fail(
        'LEARNED_AFTER_CUT',
        f'{fact.source}/{fact.subject}: learned {got.isoformat()}, which is '
        f'not strictly before the cut {c.isoformat()}. Reading it would put '
        f'information into a forecast that the forecast did not have.',
        source=fact.source, cut=c.isoformat(), learned_at=got.isoformat(),
        lag_seconds=(got - c).total_seconds())


def assert_forecast_reads_only_learned_before_cut(facts, cut) -> Outcome:
    """The gate: EVERY fact a forecast reads must predate its cut.

    Returns PASS only when the set is non-empty and every member is readable.
    An EMPTY set is refused rather than passing vacuously -- "we checked
    nothing and found no violation" is the false green this project audits
    itself for.
    """
    facts = list(facts)
    if not facts:
        return Outcome.blocked(
            'NO_FACTS_TO_JUDGE',
            'the bitemporal gate was handed an empty fact set. An empty set '
            'has no violations and that is not the same as being clean.',
            cause=Cause.DATA, cut=str(cut))
    verdicts = [(f, readable_at(f, cut)) for f in facts]
    bad = [(f, o) for f, o in verdicts if o.state is not State.PASS]
    if bad:
        return Outcome.fail(
            'FORECAST_READS_FACT_LEARNED_AFTER_CUT',
            f'{len(bad)} of {len(facts)} fact(s) are not lawful at the cut '
            f'{parse(cut).isoformat() if parse(cut) else cut!r}: '
            + '; '.join(f'{f.source}/{f.subject} -> {o.code}'
                        for f, o in bad[:6]),
            n_facts=len(facts), n_violations=len(bad),
            violations=[{'source': f.source, 'subject': f.subject,
                         'code': o.code, 'learned_at': f.learned_at}
                        for f, o in bad])
    return Outcome.ok(
        'ALL_FACTS_LAWFUL_AT_CUT', value=len(facts),
        detail=f'all {len(facts)} fact(s) were learned strictly before the '
               f'cut', n_facts=len(facts), spec_version=SPEC_VERSION)


# ----------------------------------------------------- manifest adaptation
def from_manifest_row(row: dict) -> Outcome:
    """One vintage manifest PASS row -> one `Fact`, with honest authorities.

    The two clocks are read from where the capture layer actually writes them,
    including the `value.provenance.retrieved_at` fallback that
    `vintage_selector.candidates` also has to make. A row that carries neither
    spelling produces a Fact with `learned_at=None`, which `assert_bitemporal`
    then refuses by name -- it is NOT silently dropped, because a source whose
    captures cannot be dated is exactly what a reader needs told.
    """
    if row.get('state') != 'PASS':
        return Outcome.not_applicable(
            'NOT_A_CAPTURE',
            f'manifest row is {row.get("state")}/{row.get("code")}; only a '
            f'PASS row asserts a fact about the world.',
            source=row.get('source'), state=row.get('state'))
    v = row.get('value') or {}
    prov = v.get('provenance') or {}
    scope = v.get('effective_scope') or {}
    learned = v.get('retrieved_at') or prov.get('retrieved_at')
    auth = scope.get('authority') or 'UNDECLARED'
    # E3, carried where a consumer sees it rather than left in a comment.
    if row.get('source') in ('official_inactives', 'official_injury_report'):
        auth = (f'{auth} [the recorded publication clock IS our own retrieval '
                f'time -- HTTP Date, measured lag 0.000h in 188 of 188 rows]')
    return Outcome.ok(
        'FACT_BUILT',
        value=Fact(
            subject=f'capture:{row.get("capture_id")}',
            source=row.get('source') or 'UNKNOWN',
            learned_at=learned,
            learned_at_authority='retrieved_at (HTTP response observed here)',
            valid_from=scope.get('valid_from'),
            valid_to=scope.get('valid_to'),
            valid_authority=auth,
            content_sha256=v.get('sha256'), blob=v.get('blob')),
        detail=f'{row.get("source")} @ {learned}', source=row.get('source'))


def facts_from_manifest(manifest_path=None, source: str = None) -> list:
    """Every PASS row as a `Fact`, optionally for one source. Oldest first."""
    mp = pathlib.Path(manifest_path or (_REPO / 'nfl' / 'vintage_manifest.jsonl'))
    out = []
    if not mp.exists():
        return out
    for line in mp.read_text().splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if source is not None and row.get('source') != source:
            continue
        o = from_manifest_row(row)
        if o.state is State.PASS:
            out.append(o.value)
    out.sort(key=lambda f: (f.learned_at or '', f.content_sha256 or ''))
    return out
