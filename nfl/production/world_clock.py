#!/usr/bin/env python3.12
"""A fresh file containing stale football reality must not read FRESH.

THE DEFECT THIS CLOSES. `readiness.py` measures each stage's age "from each artifact's own stated
data cutoff where it states one, and from the file modification time otherwise". Its own output then
says: *"None of the artifacts in this tree currently state a cutoff, so every age below is the
fallback."* So every freshness decision on the readiness board is mtime-only, and mtime says when a
file was WRITTEN, not what it KNOWS.

Measured on 2026-10-01, the consequence in full:

  - the 2026 play-by-play pull `pbp_2026.6643f82adb1158c8.csv.gz` was fetched 2026-09-24 15:20 and
    contains Weeks 1 and 2 only -- 2,756 and 2,733 regular-season plays, 32 games;
  - Week 3 was played 2026-09-25 to 09-28, AFTER that pull, so its results were never acquired;
  - `TEAM_GAME.json` was rebuilt 2026-09-28 01:23, four days after the pull, and so took a fresh
    mtime from a stale source;
  - `warehouse.team_game` carries a 14-day tolerance, the computed age was about 3.5 days, and the
    stage read **FRESH** while the football world had moved a full completed week past the evidence.

Nothing in that chain is lying. Each link is doing what it says. The gap is that no link compares the
evidence against the WORLD, so this module does exactly that and nothing else:

    latest_completed_game_in_world  ->  latest_completed_game_in_evidence

A GAME IS NOT COMPLETE BECAUSE ITS DATE HAS ARRIVED. Completeness here means the calendar day of the
game is strictly before the as-of day. Tonight's game is therefore NOT counted as completed, which is
the conservative direction: counting an in-progress game as complete would manufacture a spurious
evidence gap and, worse, would invite someone to go looking for its result.

THE SECOND GUARD IS LEAKAGE. The schedule legitimately carries all 272 regular-season games including
every future one, which is only safe while no outcome-bearing field is populated after the forecast
cutoff. "Safe because the columns happen to be empty" is not a guarantee, so
`assert_no_post_cutoff_outcomes` makes it one: it names every outcome field and refuses if any of them
carries a value on a game kicking off after the cutoff.

NEITHER FUNCTION FETCHES ANYTHING. Closing the evidence gap needs bytes from outside this checkout and
is the other agent's; this module's job is to make the gap impossible to miss.
"""
from __future__ import annotations

import collections
import csv
import datetime as dt
import gzip
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

TEAM_GAME = _REPO / 'nfl/warehouse/TEAM_GAME.json'

#: Outcome-bearing columns in the schedule. Named EXPLICITLY, because a leakage guard that infers
#: which fields are outcomes will miss the one that gets added next season.
SCHEDULE_OUTCOME_FIELDS = ('away_score', 'home_score', 'result', 'total', 'overtime')

#: Outcome-bearing columns in TEAM_GAME. Same reasoning. `points` is the one the simulator conditions
#: on, so it leads.
TEAM_GAME_OUTCOME_FIELDS = ('points', 'points_allowed', 'margin', 'offensive_td', 'pass_td',
                            'rush_td', 'sacks', 'turnovers', 'plays', 'pass_attempts',
                            'rush_attempts', 'targets')

#: The sentinel the warehouse writes for a field it has not acquired. A guard must treat this as
#: ABSENT, not as a value -- and must not treat a real 0 as absent, which is why the check is for this
#: exact string rather than for falsiness.
PENDING = 'UNKNOWN_PENDING_ACQUISITION'

#: The season the live product is forecasting. A gate that silently compared the wrong season would
#: report a reassuring zero gap.
CURRENT_SEASON = 2026


def _schedule_path() -> Outcome:
    from nfl.warehouse import sources
    o = sources.select(sources.registry()['schedules'])
    if o.state.value != 'PASS':
        return o
    return Outcome.ok('SCHEDULE_SELECTED', _REPO / o.value['selected'],
                      o.value['selected'], selected=o.value['selected'])


def schedule(season: int = CURRENT_SEASON) -> Outcome:
    """Every regular-season game of one season, with its calendar day and whatever score it carries."""
    sp = _schedule_path()
    if sp.state.value != 'PASS':
        return sp
    rows = []
    with gzip.open(sp.value, 'rt') as fh:
        for r in csv.DictReader(fh):
            if r.get('game_type') != 'REG' or r.get('season') != str(season):
                continue
            rows.append(r)
    if not rows:
        return Outcome.fail(
            'WORLD_CLOCK_SCHEDULE_EMPTY',
            f'the selected schedule carries no {season} regular-season games. An empty schedule is '
            f'an error, not a season with no games in it.', source=str(sp.value.name), season=season)
    return Outcome.ok('WORLD_CLOCK_SCHEDULE_READ', rows, f'{len(rows)} {season} regular-season games',
                      n=len(rows), source=sp.value.name)


def _today(as_of=None) -> dt.date:
    if as_of is None:
        return dt.datetime.now(dt.timezone.utc).date()
    if isinstance(as_of, dt.datetime):
        return as_of.date()
    if isinstance(as_of, dt.date):
        return as_of
    t = str(as_of)
    # A full UTC timestamp is the shape every other clock in this tree passes; take its date.
    if 'T' in t:
        return dt.datetime.fromisoformat(t.replace('Z', '+00:00')).date()
    return dt.date.fromisoformat(t)


def latest_completed_in_world(rows, as_of=None) -> Outcome:
    """The last game day strictly before the as-of day, and how many games fall on or before it."""
    day = _today(as_of)
    done = [r for r in rows if r.get('gameday') and r['gameday'] < day.isoformat()]
    if not done:
        return Outcome.blocked(
            'WORLD_CLOCK_NO_COMPLETED_GAME',
            f'no {CURRENT_SEASON} game has a calendar day before {day.isoformat()}, so the season has '
            f'not started and there is nothing to be behind.', cause=Cause.DATA, as_of=day.isoformat())
    last = max(r['gameday'] for r in done)
    weeks = sorted({int(r['week']) for r in done})
    return Outcome.ok('WORLD_CLOCK_WORLD_READ', {
        'latest_completed_gameday': last, 'n_completed_games': len(done),
        'completed_weeks': weeks, 'latest_completed_week': max(weeks), 'as_of': day.isoformat(),
        'IN_PROGRESS_NOT_COUNTED': ('a game whose calendar day is the as-of day is NOT counted as '
                                    'completed. Counting it would manufacture an evidence gap and '
                                    'invite someone to look for a result that does not exist yet.'),
    }, f'world is through {last} (week {max(weeks)}, {len(done)} games)')


def latest_completed_in_evidence(rows) -> Outcome:
    """The last game day for which our own warehouse actually holds a score."""
    if not TEAM_GAME.exists():
        return Outcome.blocked('WORLD_CLOCK_NO_TEAM_GAME', f'{TEAM_GAME} missing', cause=Cause.DATA)
    art = json.loads(TEAM_GAME.read_text())
    tg = art['rows'] if isinstance(art['rows'], list) else list(art['rows'].values())
    day_of = {r['game_id']: r['gameday'] for r in rows if r.get('gameday')}
    scored_days, scored_weeks, n = [], set(), 0
    for r in tg:
        if r.get('season') != CURRENT_SEASON:
            continue
        if not isinstance(r.get('points'), (int, float)):
            continue
        n += 1
        d = day_of.get(r.get('game_id'))
        if d:
            scored_days.append(d)
            scored_weeks.add(int(r['week']))
    if not scored_days:
        return Outcome.blocked(
            'WORLD_CLOCK_NO_SCORED_EVIDENCE',
            f'the warehouse holds no {CURRENT_SEASON} club-game with a numeric score that also '
            f'appears in the schedule, so the evidence frontier cannot be located. Zero is an error '
            f'here, not a frontier at the start of time.',
            cause=Cause.DATA, n_scored_club_games=n)
    last = max(scored_days)
    return Outcome.ok('WORLD_CLOCK_EVIDENCE_READ', {
        'latest_scored_gameday': last, 'n_scored_club_games': n,
        'scored_weeks': sorted(scored_weeks), 'latest_scored_week': max(scored_weeks),
    }, f'evidence is through {last} (week {max(scored_weeks)}, {n} club-games)')


def semantic_freshness(as_of=None, rows=None) -> Outcome:
    """Does our evidence reach the football world? FAILs naming the weeks that are missing.

    This is a FAIL and not a DEFERRED. A missing completed week is not an outstanding errand that the
    pipeline may proceed around -- it is the forecast resting on a world that no longer exists, and
    every projection built on it is wrong in a way no downstream check can see.
    """
    # `rows` is injectable so the gate can be exercised against a SEEDED world rather than only
    # against the real one. A guard only ever run on live data is a guard whose failure path is
    # untested, and this one's failure path is the whole point of it.
    src = None
    if rows is None:
        s = schedule()
        if s.state.value != 'PASS':
            return s
        rows = s.value
        src = s.evidence.get('source') if s.evidence else None
    w = latest_completed_in_world(rows, as_of)
    if w.state.value != 'PASS':
        return w
    e = latest_completed_in_evidence(rows)
    if e.state.value != 'PASS':
        return e

    world_week = w.value['latest_completed_week']
    evid_week = e.value['latest_scored_week']
    missing_weeks = [wk for wk in w.value['completed_weeks'] if wk > evid_week]
    missing_games = sorted(r['game_id'] for r in rows
                           if int(r['week']) in missing_weeks
                           and r.get('gameday') and r['gameday'] < w.value['as_of'])
    common = {
        'as_of': w.value['as_of'],
        'latest_completed_game_in_world': w.value['latest_completed_gameday'],
        'latest_completed_game_in_evidence': e.value['latest_scored_gameday'],
        'latest_completed_week_in_world': world_week,
        'latest_completed_week_in_evidence': evid_week,
        'n_scored_club_games': e.value['n_scored_club_games'],
        'schedule_source': src,
    }
    if not missing_weeks:
        return Outcome.ok('EVIDENCE_REACHES_THE_WORLD', common,
                          f'evidence through week {evid_week}, world through week {world_week}',
                          **common)
    return Outcome.fail(
        'EVIDENCE_BEHIND_THE_WORLD',
        f'the football world is through week {world_week} and our evidence stops at week {evid_week}. '
        f'{len(missing_weeks)} completed week(s) and {len(missing_games)} played game(s) are absent. '
        f'A file rebuilt today from a source pulled before those games carries a fresh mtime and no '
        f'new football, so an mtime-based freshness check reads FRESH and is wrong.',
        **common, missing_weeks=missing_weeks, n_missing_games=len(missing_games),
        missing_games=missing_games[:20],
        WOULD_RESOLVE_IT=('a play-by-play and schedule pull covering the missing weeks. That needs '
                          'bytes from outside this checkout and is the other agent\'s to fetch.'))


def for_target(season: int, week: int, as_of=None, rows=None) -> Outcome:
    """Does our evidence hold every game a week-`week` forecast consumes?

    `semantic_freshness` asks whether evidence reaches the WORLD, and the world's latest week counts
    as completed once any game in it is played. On the Saturday before a Sunday slate, Thursday's
    game of the SAME week makes it fail -- for a slate whose projections read only weeks < `week`.
    Wired into readiness as-is it would refuse every Sunday after a Thursday game, a false red that
    teaches people to ignore it. This is the slate-relative question, per GAME, not per week max:
    every game of an earlier week whose calendar day is before `as_of` must carry a score in the
    warehouse. Same-week games already played are reported and do not block, because the model's
    current-season state for week W is built through week W-1.
    """
    if rows is None:
        sc = schedule(season)
        if sc.state.value != 'PASS':
            return sc
        rows = sc.value
    day = _today(as_of).isoformat()
    need = [r for r in rows if str(r.get('season', season)) == str(season)
            and int(r['week']) < int(week) and r.get('gameday') and r['gameday'] < day]
    if not need:
        return Outcome.blocked(
            'SLATE_FRESHNESS_EMPTY_INPUT',
            f'no game of {season} weeks < {week} has a calendar day before {day}; there is nothing '
            f'the week-{week} forecast consumes, so freshness was not measured.',
            cause=Cause.EMPTY_INPUT, season=season, week=week, as_of=day)
    if not TEAM_GAME.exists():
        return Outcome.blocked('WORLD_CLOCK_NO_TEAM_GAME', f'{TEAM_GAME} missing', cause=Cause.DATA)
    art = json.loads(TEAM_GAME.read_text())
    tg = art['rows'] if isinstance(art['rows'], list) else list(art['rows'].values())
    scored = {}
    for r in tg:
        if r.get('season') == season and isinstance(r.get('points'), (int, float)):
            scored[r.get('game_id')] = scored.get(r.get('game_id'), 0) + 1
    missing = sorted(r['game_id'] for r in need if scored.get(r['game_id'], 0) < 2)
    same_week_played = sorted(r['game_id'] for r in rows
                              if int(r['week']) == int(week) and r.get('gameday')
                              and r['gameday'] < day)
    ev = {'season': season, 'target_week': week, 'as_of': day, 'n_games_consumed': len(need),
          'n_games_scored': len(need) - len(missing), 'missing_games': missing[:40],
          'same_week_games_already_played': same_week_played,
          'SAME_WEEK_NOTE': ('games of the target week already played are not inputs to the week-'
                             f'{week} forecast and do not block it')}
    if missing:
        return Outcome.fail(
            'EVIDENCE_BEHIND_THE_SLATE',
            f'{len(missing)} of {len(need)} game(s) the week-{week} forecast consumes carry no score '
            f'in the warehouse: {missing[:6]}. The forecast would rest on a world that is gone.',
            cause=Cause.DATA, **ev)
    return Outcome.measured('EVIDENCE_COVERS_THE_SLATE', ev, n_measured=len(need),
                            what=f'{season} games before week {week} checked for a score',
                            detail=f'all {len(need)} game(s) of weeks < {week} are scored; '
                                   f'{len(same_week_played)} same-week game(s) already played, not consumed',
                            **ev)


def assert_no_post_cutoff_outcomes(cutoff, as_of=None, rows=None, team_game_rows=None) -> Outcome:
    """No outcome-bearing field may carry a value for a game kicking off after `cutoff`.

    The schedule holding every future game is acceptable ONLY under this condition. "Acceptable
    because the columns happen to be empty" is an observation; this is the assertion.
    """
    cut = _today(cutoff)
    if rows is None:
        s = schedule()
        if s.state.value != 'PASS':
            return s
        rows = s.value
    future = [r for r in rows if r.get('gameday') and r['gameday'] > cut.isoformat()]
    if not future:
        return Outcome.blocked(
            'LEAKAGE_CHECK_VACUOUS',
            f'no {CURRENT_SEASON} game kicks off after {cut.isoformat()}, so this check examined '
            f'nothing. A guard that inspected zero rows has not demonstrated anything.',
            cause=Cause.DATA, cutoff=cut.isoformat())
    bleeding = []
    for r in future:
        for f in SCHEDULE_OUTCOME_FIELDS:
            v = (r.get(f) or '').strip()
            if v and v != PENDING:
                bleeding.append({'game_id': r['game_id'], 'gameday': r['gameday'],
                                 'field': f, 'value': v[:40], 'source': 'SCHEDULE'})

    tg = team_game_rows
    if tg is None and TEAM_GAME.exists():
        art = json.loads(TEAM_GAME.read_text())
        tg = art['rows'] if isinstance(art['rows'], list) else list(art['rows'].values())
    if tg is not None:
        fut_ids = {r['game_id'] for r in future}
        for r in tg:
            if r.get('game_id') not in fut_ids:
                continue
            for f in TEAM_GAME_OUTCOME_FIELDS:
                v = r.get(f)
                if v is None or v == PENDING:
                    continue
                # A numeric value on a game that has not kicked off is the leak. An empty string is
                # not, and the PENDING sentinel is not.
                if isinstance(v, (int, float)) or (isinstance(v, str) and v.strip()):
                    bleeding.append({'game_id': r['game_id'], 'club': r.get('club'),
                                     'field': f, 'value': str(v)[:40], 'source': 'TEAM_GAME'})

    counted = {
        'cutoff': cut.isoformat(), 'n_future_games_examined': len(future),
        'schedule_fields_checked': list(SCHEDULE_OUTCOME_FIELDS),
        'team_game_fields_checked': list(TEAM_GAME_OUTCOME_FIELDS),
        'PENDING_SENTINEL_TREATED_AS_ABSENT': PENDING,
    }
    if bleeding:
        by = collections.Counter(b['field'] for b in bleeding)
        return Outcome.fail(
            'POST_CUTOFF_OUTCOME_PRESENT',
            f'{len(bleeding)} outcome-bearing value(s) exist on games kicking off after '
            f'{cut.isoformat()}. A forecast made at this cutoff could consume them, which is leakage '
            f'whether or not any current code path actually reads them.',
            **counted, n_bleeding=len(bleeding), by_field=dict(by), examples=bleeding[:15])
    return Outcome.ok('NO_POST_CUTOFF_OUTCOME', counted,
                      f'{len(future)} future games carry no outcome in '
                      f'{len(SCHEDULE_OUTCOME_FIELDS) + len(TEAM_GAME_OUTCOME_FIELDS)} checked fields',
                      **counted)


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--as-of', default=None, help='ISO date to evaluate as (default: today, UTC)')
    ap.add_argument('--cutoff', default=None,
                    help='forecast cutoff for the leakage check (default: the as-of day)')
    a = ap.parse_args()
    f = semantic_freshness(a.as_of)
    print(f'{f.state.value} {f.code}')
    print(f'  {f.detail}')
    for k in ('latest_completed_game_in_world', 'latest_completed_game_in_evidence',
              'latest_completed_week_in_world', 'latest_completed_week_in_evidence',
              'missing_weeks', 'n_missing_games'):
        v = (f.evidence or {}).get(k)
        if v is not None:
            print(f'  {k:38s} {v}')
    g = assert_no_post_cutoff_outcomes(a.cutoff or a.as_of or dt.date.today().isoformat())
    print(f'{g.state.value} {g.code}')
    print(f'  {g.detail}')
    return 0 if f.state.value == 'PASS' and g.state.value == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
