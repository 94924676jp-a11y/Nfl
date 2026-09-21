"""A run may not claim a cut it has not reached, and a gate must test freshness.

TWO DEFECTS FROM 2026-09-21, BOTH CAUGHT BY THE OWNER READING THE ARTIFACT

1. THE COMMITTED CHAIN ARTIFACT CLAIMED A FUTURE CUT. It recorded
   `ran_at = 18:44:48Z` and `information_cut = 19:52:00Z`: an information
   cutoff fifty-one minutes after the run that produced it. A forecast cannot
   condition on information it has not reached. Nothing downstream could
   detect this, because nothing compared the two fields.

2. THE FRESHNESS GATE DID NOT TEST FRESHNESS. It read

       PASS if every source has a calculable age

   which passes a twenty-eight-hour-old injury file, and a three-day-old one
   just the same. Existence of an age is not a bound on it. That is a textbook
   false green and it was sitting on the word FRESHNESS.

WHAT THIS MODULE ASSERTS

`certify(information_cut, run_started_at, sources)` returns a certificate and
refuses on any of:

    information_cut  >  run_started_at          a future cut
    retrieved_at     >  information_cut         evidence from after the cut
    published_at     >  information_cut         same, on the publication clock
    an unparseable clock anywhere

`check_freshness` then measures each family's age against the GOVERNED
requirement in `governed_thresholds`, and -- this is the part that was missing
-- a family whose requirement is merely CANDIDATE cannot pass, however fresh
it is. A threshold nobody has validated does not certify anything, and a gate
that treats it as though it does is measuring the threshold's existence rather
than the evidence's freshness.

Nothing here has a default. A missing requirement refuses; an unknown age
refuses; a future timestamp refuses.
"""
from __future__ import annotations

import datetime as _dt
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.universe import governed_thresholds as GT      # noqa: E402
from sportsplatform.governance.outcome import (                    # noqa: E402
    Cause, Outcome)

SPEC_VERSION = 'nfl-chronology-and-freshness-1'

FRESH = 'FRESH'
STALE = 'STALE'
AGE_UNKNOWN = 'AGE_UNKNOWN'
FUTURE_DATED = 'FUTURE_DATED'
NO_REQUIREMENT = 'NO_GOVERNED_REQUIREMENT'
REQUIREMENT_UNCERTIFIED = 'REQUIREMENT_NOT_PRODUCTION_CERTIFIED'


def parse(ts):
    """A timestamp or None. There is no lenient reading of a clock."""
    if ts in (None, ''):
        return None
    try:
        t = _dt.datetime.fromisoformat(str(ts).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=_dt.timezone.utc)


def certify(information_cut, run_started_at, sources=None) -> Outcome:
    """The chronology certificate for one run.

    `sources` maps family -> {'retrieved_at': ..., 'published_at': ...}, the
    shape the player universe already emits.
    """
    cut, ran = parse(information_cut), parse(run_started_at)
    if cut is None or ran is None:
        return Outcome.blocked(
            'CHRONOLOGY_CLOCK_UNPARSEABLE',
            f'information_cut={information_cut!r} run_started_at='
            f'{run_started_at!r}. A run without two readable clocks cannot be '
            f'placed in time, and an artifact that cannot be placed in time '
            f'is not point-in-time evidence.',
            cause=Cause.GOVERNANCE,
            information_cut=information_cut, run_started_at=run_started_at)

    violations = []
    lead_s = (cut - ran).total_seconds()
    if lead_s > 0:
        violations.append({
            'kind': 'CUT_AFTER_RUN',
            'information_cut': cut.isoformat(),
            'run_started_at': ran.isoformat(),
            'seconds_into_the_future': lead_s,
            'why': ('a run cannot condition on information it has not '
                    'reached. A forecast is not a scheduled artifact and '
                    'cannot borrow one\'s licence to name a future cut.')})

    per_source = {}
    for fam, src in sorted((sources or {}).items()):
        rec = {'family': fam}
        for clock in ('retrieved_at', 'published_at'):
            raw = (src or {}).get(clock)
            t = parse(raw)
            rec[clock] = raw
            rec[f'{clock}_parsed'] = bool(t) if raw is not None else None
            if raw is not None and t is None:
                violations.append({
                    'kind': 'VINTAGE_CLOCK_UNPARSEABLE', 'family': fam,
                    'clock': clock, 'value': raw})
            elif t is not None and t > cut:
                violations.append({
                    'kind': 'VINTAGE_AFTER_CUT', 'family': fam,
                    'clock': clock, 'value': t.isoformat(),
                    'information_cut': cut.isoformat(),
                    'seconds_after_cut': (t - cut).total_seconds(),
                    'why': ('evidence retrieved or published after the cut '
                            'is evidence the run was not entitled to see.')})
            if t is not None:
                rec[f'{clock}_hours_before_cut'] = (
                    cut - t).total_seconds() / 3600.0
        per_source[fam] = rec

    val = {
        'spec_version': SPEC_VERSION,
        'information_cut': cut.isoformat(),
        'run_started_at': ran.isoformat(),
        'cut_is_before_run_by_seconds': -lead_s,
        'sources': per_source,
        'invariants_asserted': [
            'information_cut <= run_started_at',
            'every vintage retrieved_at <= information_cut',
            'every vintage published_at <= information_cut where present',
        ],
    }
    if violations:
        return Outcome.blocked(
            'CHRONOLOGY_VIOLATED',
            f'{len(violations)} chronology violation(s): '
            f'{sorted({v["kind"] for v in violations})}. An artifact that '
            f'claims information it had not reached is not point-in-time '
            f'evidence, whatever else is true of it.',
            cause=Cause.GOVERNANCE, violations=violations, **val)
    return Outcome.ok('CHRONOLOGY_CERTIFIED', value=val, **val)


def check_freshness(information_cut, sources) -> Outcome:
    """Every family's age against its GOVERNED requirement, and the requirement's
    certification against the only state that clears.

    A family passes only when all three hold: a requirement is declared, the
    requirement is PRODUCTION_CERTIFIED, and the measured age is within it.
    Any one missing is a refusal with its own name.
    """
    cut = parse(information_cut)
    if cut is None:
        return Outcome.blocked(
            'FRESHNESS_CUT_UNPARSEABLE',
            f'{information_cut!r} is not a timestamp, so no age can be '
            f'measured against it.', cause=Cause.GOVERNANCE)
    if not sources:
        return Outcome.blocked(
            'FRESHNESS_NO_SOURCES',
            'no evidence families were supplied, so there is nothing whose '
            'freshness could be established. An empty check is not a passing '
            'check.', cause=Cause.DEPENDENCY)

    rows, failing = [], []
    for fam, src in sorted(sources.items()):
        req = GT.freshness_requirement(fam)
        t = parse((src or {}).get('retrieved_at'))
        age = (cut - t).total_seconds() / 3600.0 if t else None
        if t is None:
            state = AGE_UNKNOWN
        elif age < 0:
            state = FUTURE_DATED
        elif req['max_age_hours'] is None:
            state = NO_REQUIREMENT
        elif age > req['max_age_hours']:
            state = STALE
        elif not GT.is_clearing(req['certification']):
            state = REQUIREMENT_UNCERTIFIED
        else:
            state = FRESH
        row = {
            'family': fam, 'retrieved_at': (src or {}).get('retrieved_at'),
            'age_hours': age,
            'max_age_hours': req['max_age_hours'],
            'requirement_certification': req['certification'],
            'state': state,
            'within_candidate_requirement': (
                None if (age is None or req['max_age_hours'] is None)
                else age <= req['max_age_hours']),
        }
        if state == NO_REQUIREMENT:
            row['why'] = req.get('why_absent')
        elif state == REQUIREMENT_UNCERTIFIED:
            row['why'] = (
                f'the capture is {age:.2f}h old against a proposed maximum '
                f'of {req["max_age_hours"]}h, so it is within the CANDIDATE '
                f'requirement -- but a threshold nobody has validated '
                f'certifies nothing, and passing on it would be measuring '
                f'the threshold\'s existence rather than the evidence\'s '
                f'freshness.')
            row['certification_requires'] = req.get('certification_requires')
        elif state == STALE:
            row['why'] = (f'{age:.2f}h old against a proposed maximum of '
                          f'{req["max_age_hours"]}h')
        elif state == FUTURE_DATED:
            row['why'] = (f'retrieved {-age:.2f}h AFTER the information cut, '
                          f'which is evidence this run was not entitled to '
                          f'see')
        rows.append(row)
        if state != FRESH:
            failing.append(row)

    val = {'spec_version': SPEC_VERSION, 'information_cut': cut.isoformat(),
           'families': rows, 'n_families': len(rows),
           'n_fresh': sum(1 for r in rows if r['state'] == FRESH),
           'n_within_candidate_requirement': sum(
               1 for r in rows if r['within_candidate_requirement'])}
    if failing:
        kinds = sorted({r['state'] for r in failing})
        worst = 'FAIL' if any(r['state'] in (STALE, FUTURE_DATED)
                              for r in failing) else 'BLOCKED'
        msg = (f'{len(failing)} of {len(rows)} evidence families do not '
               f'certify fresh: {kinds}. ' + '; '.join(
                   f'{r["family"]} '
                   + (f'{r["age_hours"]:.2f}h' if r['age_hours'] is not None
                      else 'age unknown')
                   + f' [{r["state"]}]' for r in failing))
        if worst == 'FAIL':
            return Outcome.fail('FRESHNESS_NOT_ESTABLISHED', msg,
                                cause=Cause.DATA, failing=failing, **val)
        return Outcome.blocked('FRESHNESS_NOT_ESTABLISHED', msg,
                               cause=Cause.GOVERNANCE, failing=failing, **val)
    return Outcome.ok('FRESHNESS_ESTABLISHED', value=val, **val)
