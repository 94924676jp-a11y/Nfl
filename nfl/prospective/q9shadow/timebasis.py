"""One canonical time basis for the prospective ordering, and refusals for the
three ways it silently goes wrong.

    retrieved_at  <=  written_at  <  kickoff

THAT ORDERING IS THE WHOLE CLAIM, and it is a comparison between three
timestamps that arrive from three different places: a capture manifest, the
forecast run's own clock, and a schedule file whose times are published in
US/Eastern. Comparing them is only meaningful if they are on one basis.

THREE FAILURE MODES, EACH REFUSED BY NAME, BECAUSE THEY FAIL DIFFERENTLY

1. NAIVE / AWARE MIXING. Python refuses `naive < aware` with a TypeError --
   which is the lucky case. The unlucky case is a string comparison:
   '2026-09-12T20:00:00' < '2026-09-12T21:00:00Z' is True by lexicography and
   means nothing, and this repository compares ISO strings in several places.
   A mixed pair is refused here rather than compared.

2. AN AMBIGUOUS NAIVE TIMESTAMP. A timestamp with no offset does not denote an
   instant. It may be admitted ONLY when the source contract names its zone,
   and it is normalised to UTC before any comparison. `CONTRACTS` is that
   declaration; a naive timestamp from a source with no entry is refused.

3. OFFSETS THAT ARE NOT UTC. `2026-09-13T13:00:00-04:00` and
   `2026-09-13T17:00:00Z` are the SAME INSTANT and compare equal -- but only
   after conversion. Everything is converted to UTC first, so an
   offset-carrying timestamp can never be ordered by its wall-clock digits.

WHY NOT JUST USE THE EXISTING PARSERS. `artifact._p`, `seal._parse` and
`postgame` each do their own `fromisoformat` with a `Z` swap and each assumes
UTC for a naive value. Assuming UTC is the thing this module refuses: it is
right often enough to hide the case where it is wrong. Those parsers keep
their behaviour; this is the gate the prospective ordering runs through, and
it is asserted against them in the suite.
"""
from __future__ import annotations

import datetime as dt
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State     # noqa: E402

SPEC_VERSION = 'q9-time-basis-1'

# THE CANONICAL BASIS. One zone, named once, used for every comparison.
CANONICAL_TZ = dt.timezone.utc
CANONICAL_TZ_NAME = 'UTC'

# Sources whose timestamps may legitimately arrive without an offset, and the
# zone their contract defines. A naive timestamp from a source not listed here
# is REFUSED -- not defaulted to UTC.
#
# `nflverse_schedule` is the one that matters: `gameday` + `gametime` are
# published in US/Eastern with no offset, and the regular season spans the DST
# change. `schedule_pregame` converts through zoneinfo before this module ever
# sees the value; the entry exists so that a raw wall-clock value arriving
# here is normalised by contract rather than guessed.
CONTRACTS = {
    'nflverse_schedule': {
        'tz': 'America/New_York',
        'why': 'nflverse publishes gameday/gametime in US/Eastern with no '
               'offset; the season spans the DST change, so a fixed offset '
               'would be wrong for part of it',
    },
    'forecast_run_clock': {
        'tz': 'UTC',
        'why': 'the forecast run stamps written_at from '
               'datetime.now(timezone.utc)',
    },
}

NAIVE_MIXED = 'TIME_BASIS_NAIVE_AWARE_MIXED'
NAIVE_UNCONTRACTED = 'TIME_BASIS_NAIVE_WITHOUT_SOURCE_CONTRACT'
UNPARSEABLE = 'TIME_BASIS_UNPARSEABLE'
ORDER_WRITTEN_AFTER_KICKOFF = 'TIME_BASIS_WRITTEN_AT_NOT_BEFORE_KICKOFF'
ORDER_RETRIEVED_AFTER_WRITTEN = 'TIME_BASIS_RETRIEVED_AFTER_WRITTEN_AT'


def is_aware(d) -> bool:
    return isinstance(d, dt.datetime) and d.tzinfo is not None \
        and d.tzinfo.utcoffset(d) is not None


def parse(value, *, source=None, field='timestamp'):
    """(datetime in UTC, basis) or an Outcome refusing it.

    `basis` is one of OFFSET_PRESENT or CONTRACT:<tz> -- so a later reader can
    see WHY a value is on the canonical basis rather than assuming it was
    always there.
    """
    if isinstance(value, dt.datetime):
        d = value
    else:
        try:
            d = dt.datetime.fromisoformat(str(value).strip().replace('Z',
                                                                     '+00:00'))
        except (TypeError, ValueError) as exc:
            return Outcome.fail(
                UNPARSEABLE,
                f'{field}={value!r} is not an ISO-8601 timestamp ({exc})',
                field=field, value=str(value))
    if is_aware(d):
        return d.astimezone(CANONICAL_TZ), 'OFFSET_PRESENT'
    # ---- naive. Admissible only under a named source contract.
    c = CONTRACTS.get(source or '')
    if c is None:
        return Outcome.fail(
            NAIVE_UNCONTRACTED,
            f'{field}={value!r} carries no UTC offset and source {source!r} '
            f'declares no timezone contract. A timestamp without an offset '
            f'does not denote an instant, and assuming {CANONICAL_TZ_NAME} '
            f'here would be right often enough to hide the case where it is '
            f'wrong.',
            field=field, value=str(value), source=source,
            contracted_sources=sorted(CONTRACTS))
    try:
        import zoneinfo
        zone = (CANONICAL_TZ if c['tz'] == 'UTC'
                else zoneinfo.ZoneInfo(c['tz']))
    except Exception as exc:                                  # noqa: BLE001
        return Outcome.fail(UNPARSEABLE,
                            f'{field}: contract zone {c["tz"]!r} unusable '
                            f'({exc})', field=field)
    return d.replace(tzinfo=zone).astimezone(CANONICAL_TZ), f'CONTRACT:{c["tz"]}'


def normalise(values: dict, sources: dict = None) -> Outcome:
    """Every value on the canonical basis, or the first refusal.

    REFUSES A MIXED SET AS A SET, not value by value. A run where one
    timestamp is aware and another is naive-but-contracted is fine -- both end
    on UTC. A run where one is naive and UNCONTRACTED is refused even if the
    others are clean, because the comparison that matters involves all of
    them.
    """
    sources = sources or {}
    out, bases, naive_fields = {}, {}, []
    for field, v in values.items():
        got = parse(v, source=sources.get(field), field=field)
        if isinstance(got, Outcome):
            return got
        d, basis = got
        out[field], bases[field] = d, basis
        if basis.startswith('CONTRACT:'):
            naive_fields.append(field)
    aware_fields = [f for f, b in bases.items() if b == 'OFFSET_PRESENT']
    return Outcome.ok(
        'TIME_BASIS_CANONICAL', value=out,
        detail=f'{len(out)} timestamp(s) on {CANONICAL_TZ_NAME}; '
               f'{len(aware_fields)} carried an offset, '
               f'{len(naive_fields)} normalised by source contract',
        bases=bases, canonical_tz=CANONICAL_TZ_NAME,
        n_offset_present=len(aware_fields),
        n_normalised_by_contract=len(naive_fields))


def assert_prospective_order(retrieved_at, written_at, kickoff_utc,
                             sources=None) -> Outcome:
    """The one ordering, on one basis. retrieved_at may be a list.

    `retrieved_at` accepts a sequence because a forecast consumes many
    captures and the constraint binds on the LATEST of them -- checking only
    the first would pass a bundle whose newest input arrived after the
    forecast.
    """
    many = (retrieved_at if isinstance(retrieved_at, (list, tuple))
            else [retrieved_at])
    if not many:
        return Outcome.fail(
            'TIME_BASIS_NO_RETRIEVAL_CLOCK',
            'no retrieved_at was supplied. A forecast that cannot say when '
            'its inputs arrived cannot assert it predates them.')
    values = {'written_at': written_at, 'kickoff_utc': kickoff_utc}
    for i, r in enumerate(many):
        values[f'retrieved_at[{i}]'] = r
    norm = normalise(values, sources)
    if norm.state is not State.PASS:
        return norm
    v = norm.value
    w, k = v['written_at'], v['kickoff_utc']
    gots = [v[f'retrieved_at[{i}]'] for i in range(len(many))]
    newest = max(gots)
    if not w < k:
        return Outcome.fail(
            ORDER_WRITTEN_AFTER_KICKOFF,
            f'written_at {w.isoformat()} is not strictly before kickoff '
            f'{k.isoformat()} on {CANONICAL_TZ_NAME}. A forecast written at '
            f'or after kickoff is not a forecast, and there is no grace '
            f'period at any margin.',
            written_at=w.isoformat(), kickoff_utc=k.isoformat(),
            seconds_late=(w - k).total_seconds())
    late = [i for i, g in enumerate(gots) if g > w]
    if late:
        return Outcome.fail(
            ORDER_RETRIEVED_AFTER_WRITTEN,
            f'{len(late)} input(s) were retrieved after written_at '
            f'{w.isoformat()} (newest {newest.isoformat()}). The forecast '
            f'could not have used them.',
            indices=late, newest_retrieved_at=newest.isoformat(),
            written_at=w.isoformat())
    return Outcome.ok(
        'TIME_BASIS_PROSPECTIVE_ORDER_HOLDS',
        value={'newest_retrieved_at': newest.isoformat(),
               'written_at': w.isoformat(), 'kickoff_utc': k.isoformat()},
        detail=f'retrieved_at <= written_at < kickoff on '
               f'{CANONICAL_TZ_NAME}; sealed '
               f'{(k - w).total_seconds() / 3600:.2f}h before kickoff, newest '
               f'input {(w - newest).total_seconds() / 3600:.2f}h before the '
               f'write',
        bases=dict(norm.evidence['bases']),
        canonical_tz=CANONICAL_TZ_NAME,
        hours_before_kickoff=round((k - w).total_seconds() / 3600, 4),
        n_inputs=len(gots))


def audit_artifact(art) -> Outcome:
    """The ordering for one sealed artifact, from its own recorded clocks."""
    caps = art.get('source_captures') or []
    if not caps:
        return Outcome.fail('TIME_BASIS_NO_SOURCE_CAPTURES',
                            f'{art.get("forecast_id")} names no input capture')
    return assert_prospective_order(
        [c.get('retrieved_at') for c in caps],
        art.get('written_at'), art.get('kickoff_utc'))
