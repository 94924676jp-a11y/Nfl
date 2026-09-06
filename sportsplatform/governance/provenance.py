"""Five timestamps that must never be conflated. Rule 002 made executable.

V7's weather layer is the worked example of why this needs a type rather than a
convention. It served forecasts from a 30-minute cache and stamped a NEW
`generated_utc` on every book it assembled. Downstream, one guard read
`generated_utc`, found it seconds old, and certified the slate as fresh -- while
the forecasts inside it were half an hour stale. The guard was not wrong about
the field it read. It was reading the wrong field, because the artifact only
had one.

So V8 keeps them apart by construction:

    source_timestamp    when the SOURCE says the data describes
    retrieved_at        when WE actually obtained the bytes
    cache_timestamp     when the cached copy was written (None if live)
    generated_at        when the artifact WRAPPING it was assembled
    effective_for_date  the game date this may lawfully be used for

`generated_at` is the youngest and the most useless for freshness -- it is the
timestamp on the envelope, not the letter. Asking this object "how old are
you?" is therefore refused: you must ask which clock.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
from typing import Optional

from .outcome import Cause, Outcome, State

_REQUIRED = ('source', 'source_timestamp', 'retrieved_at', 'generated_at',
             'effective_for_date', 'schema_version')


def _parse(ts, field):
    if isinstance(ts, dt.datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=dt.timezone.utc)
    try:
        d = dt.datetime.fromisoformat(str(ts).replace('Z', '+00:00'))
    except (ValueError, TypeError) as exc:
        raise ValueError(f'{field}={ts!r} is not a timestamp ({exc})')
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


@dataclasses.dataclass(frozen=True)
class Provenance:
    source: str
    source_timestamp: str
    retrieved_at: str
    generated_at: str
    effective_for_date: str
    schema_version: str
    cache_timestamp: Optional[str] = None
    url: Optional[str] = None

    def age_seconds(self, clock: str, now: dt.datetime = None) -> float:
        """How old, by a NAMED clock. There is no unqualified age."""
        if clock not in ('source_timestamp', 'retrieved_at', 'cache_timestamp',
                         'generated_at'):
            raise ValueError(
                f'age_seconds({clock!r}): name the clock. "How old is this" has '
                f'four different answers here and V7 shipped the wrong one.')
        v = getattr(self, clock)
        if v is None:
            raise ValueError(f'{clock} is not set on this record.')
        now = now or dt.datetime.now(dt.timezone.utc)
        return (now - _parse(v, clock)).total_seconds()

    def effective_age_seconds(self, now: dt.datetime = None) -> float:
        """The age that matters: the OLDEST real clock, never the envelope.

        A cached artifact is as old as its cache, not as young as the moment it
        was re-wrapped. This is the single computation V7's weather guard got
        wrong.
        """
        clocks = [self.source_timestamp, self.retrieved_at]
        if self.cache_timestamp:
            clocks.append(self.cache_timestamp)
        now = now or dt.datetime.now(dt.timezone.utc)
        return max((now - _parse(c, 'clock')).total_seconds() for c in clocks)


def validate(p: Provenance) -> Outcome:
    """Every required field present, parseable, and internally consistent."""
    missing = [f for f in _REQUIRED if not getattr(p, f, None)]
    if missing:
        return Outcome.blocked(
            'PROVENANCE_INCOMPLETE',
            f'{p.source or "<unnamed source>"} is missing {missing}. A field '
            f'without provenance does not enter the model.', missing=missing, cause=Cause.DATA)
    try:
        src = _parse(p.source_timestamp, 'source_timestamp')
        got = _parse(p.retrieved_at, 'retrieved_at')
        gen = _parse(p.generated_at, 'generated_at')
        cache = _parse(p.cache_timestamp, 'cache_timestamp') \
            if p.cache_timestamp else None
    except ValueError as exc:
        return Outcome.blocked('PROVENANCE_UNPARSEABLE', str(exc), cause=Cause.DATA)

    # We cannot have retrieved data before the source produced it.
    if got < src:
        return Outcome.fail(
            'PROVENANCE_IMPOSSIBLE',
            f'retrieved_at {p.retrieved_at} precedes source_timestamp '
            f'{p.source_timestamp}. One of the two clocks is wrong and '
            f'guessing which would launder the error.')
    # A cache hit that claims to have been retrieved now is the V7 defect.
    if cache is not None and abs((got - cache).total_seconds()) > 1.0:
        return Outcome.fail(
            'CACHE_RETRIEVAL_CONFLATED',
            f'this record was served from a cache written at '
            f'{p.cache_timestamp} but reports retrieved_at {p.retrieved_at}. '
            f'A cache hit was not retrieved now -- reporting it as though it '
            f'was is exactly how a 30-minute-old forecast passed a freshness '
            f'check.')
    if gen < got:
        return Outcome.fail(
            'PROVENANCE_IMPOSSIBLE',
            f'generated_at {p.generated_at} precedes retrieved_at '
            f'{p.retrieved_at}; the wrapper cannot predate its contents.')
    return Outcome.ok('PROVENANCE_VALID', dataclasses.asdict(p),
                      detail=f'{p.source} provenance is complete and consistent')


def assert_usable_for(p: Provenance, game_date: str,
                      max_effective_age_s: float = None,
                      now: dt.datetime = None) -> Outcome:
    """May this record be used for a game on `game_date`?

    Two independent questions, deliberately not merged:
      leakage  -- does it contain information from on or after the game?
      staleness -- is its OLDEST clock too old to be current?
    """
    v = validate(p)
    if v.state is not State.PASS:
        return v
    if p.effective_for_date != game_date:
        return Outcome.blocked(
            'PROVENANCE_WRONG_DATE',
            f'record is effective for {p.effective_for_date}, asked for '
            f'{game_date}.', cause=Cause.DATA)
    src = _parse(p.source_timestamp, 'source_timestamp')
    game = _parse(f'{game_date}T00:00:00+00:00', 'game_date')
    if src >= game:
        return Outcome.fail(
            'PROVENANCE_LEAKAGE',
            f'source_timestamp {p.source_timestamp} is on or after the game '
            f'date {game_date}. This record contains the outcome it would be '
            f'used to predict.')
    if max_effective_age_s is not None:
        age = p.effective_age_seconds(now)
        if age > max_effective_age_s:
            return Outcome.fail(
                'PROVENANCE_STALE',
                f'oldest clock is {age:.0f}s old against a bound of '
                f'{max_effective_age_s:.0f}s. Measured on the oldest real '
                f'clock, not on generated_at, which only dates the wrapper.',
                effective_age_seconds=age)
    return Outcome.ok('PROVENANCE_USABLE', dataclasses.asdict(p),
                      detail=f'{p.source} usable for {game_date}')
