"""Staleness per source, measured against KICKOFF. P7 Part B.

WHAT THIS ANSWERS AND WHAT IT REFUSES TO ANSWER

For one game, for each registered source: how old was the newest capture we
could LAWFULLY have read at that kickoff? That is the question a reader of a
forecast wants and the one no existing artifact answers -- `coverage` answers
"was the obligation discharged", which is about declared targets, and
`registry.unmet_targets` answers "has this source ever been captured at all",
which has no time dimension and no game dimension.

Age at kickoff is a third thing again. A source can have discharged nothing and
still be four minutes old; it can have a clean coverage row and be eight days
stale. Those need opposite responses.

NO INVENTED THRESHOLD. THIS IS THE PART THAT WOULD HAVE BEEN EASY TO GET WRONG.

A freshness monitor needs a line, and a line that someone picked is a silent
constant. So there is no default staleness budget here. A source is GRADED only
where an obligation already declares one, and the budget is DERIVED from that
declaration rather than restated:

    budget(source) = max over kinds the source serves of
                     schedule.WINDOWS[kind] width

`schedule.WINDOWS` is where this project already wrote down how long a capture
remains the current vintage -- 80 minutes for `inactives`, 20 hours for
`practice` and `final_status`. A source that serves no kind gets no grade at
all: it is reported with its measured age and the named state
NO_DECLARED_FRESHNESS_OBLIGATION. Reporting an age without grading it is the
honest output; picking 24 hours because it sounds reasonable is not.

TRANSACTION TIME, NOT PUBLICATION TIME

Staleness is measured on `retrieved_at` through `bitemporal.readable_at`, so a
DATE-granularity clock refuses instead of being read as midnight. A source
whose captures we cannot date is NOT fresh and NOT stale: it is
UNDATEABLE_CAPTURE, which is a capture defect and needs saying so.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from nfl.capture import bitemporal as BT                            # noqa: E402
from nfl.capture import registry as REG                             # noqa: E402
from nfl.capture.schedule import WINDOWS                            # noqa: E402

SPEC_VERSION = 'freshness-1'

# The closed vocabulary. A verdict outside it is a bug, not a nuance.
FRESH = 'FRESH'                       # graded, and inside its derived budget
STALE = 'STALE'                       # graded, and older than its budget
UNGRADED = 'NO_DECLARED_FRESHNESS_OBLIGATION'   # serves no kind; age reported
NO_LAWFUL = 'NO_LAWFUL_CAPTURE_BEFORE_KICKOFF'  # captures exist, all too late
NEVER = 'NEVER_CAPTURED'              # no PASS row for this source, ever
UNDATEABLE = 'UNDATEABLE_CAPTURE'     # PASS rows whose learned time is unusable
WATCH_ONLY = 'WATCH_ONLY_NOT_A_GAME_INPUT'
VERDICTS = (FRESH, STALE, UNGRADED, NO_LAWFUL, NEVER, UNDATEABLE, WATCH_ONLY)


def budget(name: str):
    """The staleness budget for a source, DERIVED from its serving windows.

    Returns (timedelta, derivation) or (None, reason). Never a number chosen
    here: the widths come from `schedule.WINDOWS`, which is where this project
    already recorded how long each artifact remains the current vintage.
    """
    spec = REG.BY_NAME.get(name)
    if spec is None:
        return None, f'{name!r} is not in SOURCE_REGISTRY'
    if spec.watch_only:
        return None, ('watch-only: it discharges no kind and the vintage '
                      'capture never fetches it, so no game-time obligation '
                      'exists to derive a budget from')
    kinds = [k for k in spec.serves_kinds if k in WINDOWS]
    if not kinds:
        return None, ('serves no capture kind, so this project has declared '
                      'no window within which it must be current')
    widths = {k: (WINDOWS[k][1] - WINDOWS[k][0]) for k in kinds}
    worst = max(widths.values())
    return worst, ('max over served kinds of schedule.WINDOWS width: '
                   + ', '.join(f'{k}={int(v.total_seconds() // 60)}min'
                               for k, v in sorted(widths.items())))


def _pass_facts(manifest_path, name):
    return BT.facts_from_manifest(manifest_path=manifest_path, source=name)


def source_staleness(name: str, kickoff_utc, *, manifest_path=None) -> dict:
    """One source against one kickoff. A dict, because this is a REPORT row.

    Deliberately not an Outcome: a monitor emits one row per source and the
    caller decides what a page of rows means. `monitor()` below returns the
    Outcome for the page.
    """
    ko = BT.parse(kickoff_utc)
    row = {'source': name, 'kickoff_utc': (ko.isoformat() if ko else None),
           'spec_version': SPEC_VERSION}
    if ko is None:
        row.update(verdict=UNDATEABLE,
                   detail=f'kickoff {kickoff_utc!r} is not an ISO-8601 instant')
        return row
    spec = REG.BY_NAME.get(name)
    facts = _pass_facts(manifest_path, name)
    row['n_pass_captures'] = len(facts)
    if spec is not None and spec.watch_only:
        row.update(verdict=WATCH_ONLY, age_seconds=None, budget_seconds=None,
                   detail=('watch-only source. It discharges no capture kind '
                           'and may not be read as a game input, so its age '
                           'against a kickoff is not a meaningful quantity.'))
        return row
    if not facts:
        row.update(verdict=NEVER, age_seconds=None, budget_seconds=None,
                   detail=('no PASS capture exists for this source at all. '
                           'Never captured is not stale, and it is not '
                           'covered either.'))
        return row
    lawful = []
    undateable = 0
    for f in facts:
        o = BT.readable_at(f, ko)
        if o.state is State.PASS:
            lawful.append(f)
        elif o.code in ('NO_TRANSACTION_TIME',
                        'LEARNED_TIME_GRANULARITY_TOO_COARSE'):
            undateable += 1
    row['n_undateable'] = undateable
    if not lawful:
        row.update(
            verdict=(UNDATEABLE if undateable else NO_LAWFUL),
            age_seconds=None, budget_seconds=None,
            detail=(f'{len(facts)} capture(s) exist and none is readable at '
                    f'kickoff; {undateable} of them cannot be dated at all. '
                    f'This is a true statement about what we held at kickoff, '
                    f'not a reason to widen the cut.'))
        return row
    newest = max(lawful, key=lambda f: (f.learned_at or '',
                                        f.content_sha256 or ''))
    age = ko - BT.parse(newest.learned_at)
    row.update(newest_learned_at=newest.learned_at, blob=newest.blob,
               content_sha256=newest.content_sha256,
               age_seconds=age.total_seconds(),
               age_minutes=round(age.total_seconds() / 60.0, 1),
               n_lawful=len(lawful))
    b, why = budget(name)
    row['budget_derivation'] = why if b is None else why
    if b is None:
        row.update(verdict=UNGRADED, budget_seconds=None,
                   detail=(f'age {round(age.total_seconds() / 3600.0, 2)}h at '
                           f'kickoff, REPORTED AND NOT GRADED: {why}. A '
                           f'threshold invented here would be a silent '
                           f'constant.'))
        return row
    row['budget_seconds'] = b.total_seconds()
    row['verdict'] = FRESH if age <= b else STALE
    row['detail'] = (
        f'newest lawful capture is {round(age.total_seconds() / 60.0, 1)}min '
        f'old at kickoff against a derived budget of '
        f'{int(b.total_seconds() // 60)}min ({why})')
    return row


def monitor(kickoffs: dict, *, manifest_path=None, sources=None) -> Outcome:
    """Every source against every kickoff. `kickoffs` is {game_id: iso}.

    PASS means the page was computed, NOT that everything is fresh. A monitor
    that refuses when it finds staleness cannot report staleness, and staleness
    is what it is for. The verdict counts are the finding; read them.

    An EMPTY kickoff map refuses, for the reason this project keeps paying for:
    a report over nothing has no violations and that is not the same as clean.
    """
    if not kickoffs:
        return Outcome.blocked(
            'NO_KICKOFFS_TO_MEASURE_AGAINST',
            'freshness.monitor was given no kickoffs. Staleness is measured '
            'against a kickoff; with none there is nothing to measure and an '
            'empty clean report would be a false green.',
            cause=Cause.DEPENDENCY)
    names = list(sources) if sources is not None else [s.name for s in REG.REGISTRY]
    rows, counts = [], {}
    for gid, ko in sorted(kickoffs.items()):
        for n in names:
            r = source_staleness(n, ko, manifest_path=manifest_path)
            r['game_id'] = gid
            rows.append(r)
            counts[r['verdict']] = counts.get(r['verdict'], 0) + 1
    unknown = sorted(v for v in counts if v not in VERDICTS)
    if unknown:
        return Outcome.fail(
            'FRESHNESS_VERDICT_OUTSIDE_VOCABULARY',
            f'{unknown} is not in the closed verdict vocabulary {VERDICTS}. '
            f'An unrecognised verdict is a bug in this module, not a nuance '
            f'in the data.', unknown=unknown)
    return Outcome.ok(
        'FRESHNESS_REPORT', value=rows,
        detail=f'{len(rows)} (source, game) row(s) across {len(kickoffs)} '
               f'kickoff(s); verdicts {counts}',
        n_rows=len(rows), n_games=len(kickoffs), verdict_counts=counts,
        spec_version=SPEC_VERSION,
        reading_note=('PASS means the page was computed. STALE and '
                      'NO_LAWFUL_CAPTURE_BEFORE_KICKOFF rows are findings, '
                      'not errors in this report.'))


def kickoffs_from_week_plan(season: int, week: int) -> Outcome:
    """{game_id: kickoff_iso} for one week, from the capture week plan.

    Delegates to `coverage.load_week_plan` so there is ONE reader of the
    captured schedule rather than a second one that can drift from it.
    """
    from nfl.capture import coverage as C
    plan = C.load_week_plan(season, week)
    if plan.state is not State.PASS:
        return plan
    ko = {}
    for c in plan.value:
        k = getattr(c, 'kickoff_utc', None)
        if k is None:
            continue
        ko[c.game_id] = (k.isoformat() if hasattr(k, 'isoformat') else str(k))
    if not ko:
        return Outcome.blocked(
            'WEEK_PLAN_CARRIES_NO_KICKOFF',
            f'{season} week {week}: the plan has {len(plan.value)} target(s) '
            f'and none carries a kickoff instant.',
            cause=Cause.DATA, n_targets=len(plan.value))
    return Outcome.ok('KICKOFFS_RESOLVED', value=ko,
                      detail=f'{len(ko)} game(s)', n_games=len(ko),
                      snapshot=plan.evidence.get('snapshot'))
