"""Is an injury capture complete for a week? The owner's ruling of 2026-10-02, as a pure rule.

THE DEFECT THIS REPLACES. `live_features.injury_rows` counted every row whose `report_status` was
blank as "unfilled", and the INJURY_REPORT_INCOMPLETE blocker refused on that count. Measured on the
lawful vintage: 692 rows, 518 blank -- and every one of the 518 carried a `practice_status`; none
was blank on both. In the nflverse feed `report_status` is the game-status designation (Out /
Doubtful / Questionable) and `practice_status` the practice report. A player on the practice report
with no designation has a blank `report_status` BY DEFINITION. Every NFL week has such rows, so the
old count could never reach zero and the blocker could never clear.

THE RULING, NARROWLY:
  * report_status blank + practice_status present   -> NOT incomplete by itself
  * both blank                                       -> incomplete
  * chronology is preserved: a capture can only be judged complete for a week once that week's
    designations are necessarily final, which is once every game in the week has kicked off.
    The 2026-09-24T06:07Z capture precedes week 3's first kickoff (Sep 24 20:15 ET) and stays
    INCOMPLETE for week 3; weeks 1-2 clear under the same rule.
  * nothing broader. Vintage selection, the information-set gate and the appearance contract are
    untouched.

The kickoff threshold is not an invented constant: it is the latest `gameday`+`gametime` of the
week, read from the governed schedule. Designations published Friday are certainly final by the
last kickoff; using "Friday" would be a day-count nobody measured.
"""
from __future__ import annotations

import collections
import datetime as dt
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York')

COMPLETE = 'COMPLETE'
INCOMPLETE_BOTH_BLANK = 'INCOMPLETE_BOTH_STATUSES_BLANK'
INCOMPLETE_NO_ROWS = 'INCOMPLETE_NO_INJURY_ROWS_FOR_SEASON'
INCOMPLETE_PREDATES = 'INCOMPLETE_CAPTURE_PREDATES_FINAL_DESIGNATIONS'
INCOMPLETE_NO_KICKOFF = 'INCOMPLETE_WEEK_KICKOFFS_UNKNOWN'
INCOMPLETE_STATES = (INCOMPLETE_BOTH_BLANK, INCOMPLETE_PREDATES, INCOMPLETE_NO_KICKOFF)


def _blank(v) -> bool:
    return not (v or '').strip()


def row_is_unfilled(row) -> bool:
    """Unfilled means the row says NOTHING: both statuses blank. One filled is a statement."""
    return _blank(row.get('report_status')) and _blank(row.get('practice_status'))


def kickoff_utc(sched_row) -> dt.datetime | None:
    """gameday + gametime (Eastern, as nflverse publishes them) -> aware UTC datetime."""
    d, t = sched_row.get('gameday'), sched_row.get('gametime')
    if not d or not t:
        return None
    try:
        local = dt.datetime.fromisoformat(f'{d}T{t}').replace(tzinfo=ET)
    except ValueError:
        return None
    return local.astimezone(dt.timezone.utc)


def week_final_kickoff(schedule_rows, season, week) -> dt.datetime | None:
    """The last kickoff of a week. After it, every game-status designation is final."""
    ks = [kickoff_utc(r) for r in schedule_rows
          if str(r.get('season')) == str(season) and str(r.get('week')) == str(week)]
    ks = [k for k in ks if k is not None]
    return max(ks) if ks else None


def _aware(ts) -> dt.datetime:
    if isinstance(ts, dt.datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=dt.timezone.utc)
    return dt.datetime.fromisoformat(str(ts).replace('Z', '+00:00'))


def assess(rows, observed_at, schedule_rows, season) -> dict:
    """Per-week verdicts for one capture. Pure; nothing is read from disk here.

    Returns {'by_week': {week: {'state', 'n_rows', 'n_both_blank',
    'n_report_blank_practice_present', 'final_kickoff_utc'}},
    'incomplete_weeks': [...], 'complete_weeks': [...], 'observed_at': iso}
    """
    obs = _aware(observed_at)
    byw = collections.defaultdict(list)
    for r in rows:
        if str(r.get('season')) == str(season):
            byw[str(r.get('week'))].append(r)
    out = {}
    if not byw:
        # OWNER RULE 1 (2026-10-02): no rows for the season produced an empty incomplete list,
        # which every consumer read as "all weeks complete". No rows is the strongest
        # incompleteness there is, and it is named as such with the count.
        return {'by_week': {}, 'incomplete_weeks': ['*'], 'complete_weeks': [],
                'observed_at': obs.isoformat(), 'state': INCOMPLETE_NO_ROWS, 'cause': 'EMPTY_INPUT',
                'n_rows': 0, 'n_rows_total': len(list(rows)) if hasattr(rows, '__len__') else None}
    for week, wrows in sorted(byw.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 0):
        both = sum(1 for r in wrows if row_is_unfilled(r))
        half = sum(1 for r in wrows
                   if _blank(r.get('report_status')) and not _blank(r.get('practice_status')))
        fk = week_final_kickoff(schedule_rows, season, week)
        if fk is None:
            state = INCOMPLETE_NO_KICKOFF
        elif obs < fk:
            state = INCOMPLETE_PREDATES
        elif both:
            state = INCOMPLETE_BOTH_BLANK
        else:
            state = COMPLETE
        out[week] = {'state': state, 'n_rows': len(wrows), 'n_both_blank': both,
                     'n_report_blank_practice_present': half,
                     'final_kickoff_utc': fk.isoformat() if fk else None}
    return {'by_week': out,
            'incomplete_weeks': [w for w, v in out.items() if v['state'] != COMPLETE],
            'complete_weeks': [w for w, v in out.items() if v['state'] == COMPLETE],
            'observed_at': obs.isoformat()}
