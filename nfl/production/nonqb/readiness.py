"""nonqb_readiness.report(): exactly which condition blocks execution.

DESIGNED SO A GENERIC FAILURE IS IMPOSSIBLE. Every blocking condition is
computed from the captured data and named. "It didn't work" is not an output
this module can produce.

The state it reports is deliberately finer than R2's. R2 said
WAITING_FOR_INJURIES_2026 because the feed was 404. The feed has since been
published -- and it is nearly empty. Those are different conditions and they
need different names, because the first clears itself and the second may not.
"""
from __future__ import annotations

import collections
import csv
import gzip
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Outcome             # noqa: E402
from nfl.production.nonqb import eligibility as EL                # noqa: E402

# What the frozen appearance mechanism needs, and the minimum that makes it
# runnable at all. These are structural requirements of the mechanism, not
# quality thresholds chosen to get a pass.
MIN_TEAMS_COVERED = 32          # every team on the slate must appear
NEEDS_REPORT_STATUS = True      # teammate_availability reads it


def _latest_injuries(season: int):
    man = _REPO / 'nfl' / 'vintage_manifest.jsonl'
    if not man.exists():
        return None, None
    best = None
    for line in man.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get('source') != 'injuries' or r.get('state') != 'PASS':
            continue
        v = r.get('value') or {}
        p = v.get('provenance') or {}
        ts = v.get('retrieved_at') or p.get('retrieved_at')
        if ts and (best is None or ts > best[0]):
            best = (ts, v.get('blob'))
    if best is None:
        return None, None
    path = _REPO / best[1] if best[1] else None
    if not path or not path.exists():
        return best[0], None
    txt = (gzip.open(path, 'rt').read() if str(path).endswith('.gz')
           else path.read_text())
    return best[0], list(csv.DictReader(txt.splitlines()))


def latest_injuries_rows(season: int):
    """The rows of the newest successful injuries capture, or None."""
    return _latest_injuries(season)[1]


def injuries_readiness(season: int, week: int, teams) -> dict:
    ts, rows = _latest_injuries(season)
    if ts is None:
        return {'state': f'WAITING_FOR_INJURIES_{season}',
                'reason': 'no injuries capture has ever succeeded',
                'retrieved_at': None}
    if rows is None:
        return {'state': 'INJURIES_BLOB_MISSING',
                'reason': 'the manifest records a capture whose blob is absent',
                'retrieved_at': ts}
    wk = [r for r in rows if r.get('season') == str(season)
          and r.get('week') == str(week)]
    covered = sorted({r['team'] for r in wk if r.get('team')})
    want = sorted(set(teams))
    absent = [t for t in want if t not in covered]
    pop = {c: sum(1 for r in wk if (r.get(c) or '').strip())
           for c in ('report_status', 'practice_status',
                     'practice_primary_injury')}
    d = {'retrieved_at': ts, 'n_rows': len(wk),
         'teams_covered': len(covered), 'teams_required': len(want),
         'teams_absent': absent, 'column_population': pop}
    if not wk:
        d.update(state=f'INJURIES_{season}_EMPTY_FOR_WEEK_{week}',
                 reason='the feed is published but carries no row for this '
                        'week')
        return d
    if absent:
        d.update(
            state=f'INJURIES_{season}_PUBLISHED_BUT_INSUFFICIENT',
            reason=(f'the feed is published and parses, but covers '
                    f'{len(covered)} of {len(want)} slate teams. '
                    f'teammate_availability is a team-level feature, so a team '
                    f'with no rows cannot be distinguished from a team with '
                    f'nobody injured.'))
        return d
    if NEEDS_REPORT_STATUS and pop['report_status'] == 0:
        d.update(state=f'INJURIES_{season}_REPORT_STATUS_UNFILED',
                 reason='every row carries an empty report_status; '
                        'teammate_availability reads it, and an unfiled '
                        'designation is not an absence of injury')
        return d
    d.update(state='INJURIES_READY', reason='all slate teams covered and '
                                            'report_status filed')
    return d


def report(season: int = 2026, week: int = 1, teams=None) -> dict:
    """The single call an operator makes to learn what is blocking."""
    teams = sorted(teams) if teams else _slate_teams(season, week)
    inj = injuries_readiness(season, week, teams)
    inputs = {}
    for layer, needs in EL.REQUIRED_INPUTS.items():
        for n in needs:
            if 'injuries_' in n:
                inputs[n] = ('AVAILABLE' if inj['state'] == 'INJURIES_READY'
                             else 'MISSING')
    mx = EL.matrix(inputs)
    blocking = [l for l, v in mx.items()
                if v['allowed_runtime_role'] == 'BLOCKED']
    return {
        'artifact': 'NONQB_READINESS',
        'season': season, 'week': week, 'n_teams': len(teams),
        'overall_state': (inj['state'] if blocking else 'ENGINE_INPUTS_READY'),
        'blocking_layers': blocking,
        'injuries': inj,
        'eligibility': mx,
        'gates': json.loads(EL.STATE.read_text())['gates'],
        'next_action': _next_action(inj),
        'game_readiness': game_readiness(season, week),
        'future_requirements': future_requirements(season, week),
    }


def _next_action(inj) -> str:
    s = inj['state']
    if s.startswith('WAITING_FOR_INJURIES'):
        return ('none: the capture workflow already polls the feed and will '
                'record it when it publishes. No code change is required.')
    if s.endswith('PUBLISHED_BUT_INSUFFICIENT'):
        return (f'none in code. The feed covers {inj["teams_covered"]} of '
                f'{inj["teams_required"]} slate teams; the remaining teams file '
                f'their reports later in the game week and the periodic capture '
                f'will pick them up. Re-run readiness then.')
    if s.endswith('REPORT_STATUS_UNFILED'):
        return ('none in code. Game-status designations are filed later in the '
                'week; the capture path will record them.')
    if s == 'INJURIES_READY':
        return ('run the slate. D2 executes on the real source and D3-D5 '
                'follow without a code change.')
    return 'inspect the manifest: the capture record and the blob disagree.'


def _slate_teams(season, week):
    from nfl.capture import coverage as C
    p = C.load_week_plan(season, week)
    if p.state.name != 'PASS':
        return []
    out = set()
    for c in p.value:
        parts = c.game_id.split('_')
        out.update(parts[2:4])
    return sorted(out)


# =====================================================================
# R4 section G: readiness is a PER-GAME property, not a slate property.
#
# The slate dashboard ("2 of 32 teams covered") is the right thing to show an
# operator and the wrong thing to gate execution on. Two teams that have both
# filed can be forecast while thirty have not, and holding them back is a
# scheduling decision masquerading as a modelling one.
#
# NOTHING BELOW LOWERS THE FEATURE REQUIREMENT. A game executes D2 only when
# BOTH participating teams satisfy the same frozen input contract the slate
# check applies. What changes is the granularity of the answer.
# =====================================================================

# Declared, not tuned. A team's block is stale when the feed has been
# refreshed well past it and that team's rows have not moved -- 48 hours is
# long enough to span a normal practice-report cadence and short enough to
# catch a block that stopped updating.
STALE_HOURS = 48.0

GAME_STATES = (
    'READY_WITH_COMPLETE_INPUT',       # both teams, every contract field filed
    'READY',                           # both teams satisfy the contract
    'INJURY_REPORT_NOT_YET_FILED',     # a team has no row for this week at all
    'INJURY_REPORT_INCOMPLETE',        # rows exist, a contract field is unfilled
    'INJURY_REPORT_STALE',             # the feed moved on, this block did not
    'INJURY_REPORT_CHRONOLOGY_FAILURE',  # the capture is not before kickoff
)
# Worst-first: a game takes the worst state of its two teams.
_SEVERITY = {s: i for i, s in enumerate(reversed(GAME_STATES))}


def _parse_ts(t):
    import datetime as dt
    if not t:
        return None
    try:
        d = dt.datetime.fromisoformat(str(t).replace('Z', '+00:00'))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def _all_injury_captures(season: int):
    """Every successful injuries capture, newest first, with its rows.

    Per-team staleness cannot be read off the newest capture alone: it is a
    statement about WHEN a team's block last changed, so every capture has to
    be opened.
    """
    man = _REPO / 'nfl' / 'vintage_manifest.jsonl'
    if not man.exists():
        return []
    out = []
    for line in man.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get('source') != 'injuries' or r.get('state') != 'PASS':
            continue
        v = r.get('value') or {}
        p = v.get('provenance') or {}
        ts = v.get('retrieved_at') or p.get('retrieved_at')
        blob = v.get('blob')
        if not ts or not blob:
            continue
        path = _REPO / blob
        if not path.exists():
            continue
        out.append((ts, path))
    out.sort(key=lambda x: x[0], reverse=True)
    return out


_CAPTURE_CACHE: dict = {}


def team_report_history(season: int, week: int):
    """team -> {newest_capture_with_rows, n_rows, column population}."""
    key = (season, week)
    if key in _CAPTURE_CACHE:
        return _CAPTURE_CACHE[key]
    seen, newest_overall = {}, None
    for ts, path in _all_injury_captures(season):
        if newest_overall is None:
            newest_overall = ts
        txt = (gzip.open(path, 'rt').read() if str(path).endswith('.gz')
               else path.read_text())
        rows = [r for r in csv.DictReader(txt.splitlines())
                if r.get('season') == str(season) and r.get('week') == str(week)]
        by_team = collections.defaultdict(list)
        for r in rows:
            if r.get('team'):
                by_team[r['team']].append(r)
        for t, rs in by_team.items():
            if t in seen:            # captures are newest-first
                continue
            seen[t] = {'newest_capture': ts, 'n_rows': len(rs),
                       'blob': str(path.relative_to(_REPO)),
                       'population': {
                           c: sum(1 for r in rs if (r.get(c) or '').strip())
                           for c in ('report_status', 'practice_status',
                                     'practice_primary_injury')}}
    _CAPTURE_CACHE[key] = (seen, newest_overall)
    return _CAPTURE_CACHE[key]


def cache_clear():
    _CAPTURE_CACHE.clear()


def team_readiness(season: int, week: int, team: str, kickoff_utc=None,
                   written_at=None) -> dict:
    """One team's state against the frozen input contract."""
    seen, newest_overall = team_report_history(season, week)
    d = seen.get(team)
    if d is None:
        # ABSENCE IS ABSENCE. A team with no filed report is NOT a team with
        # nobody injured, and teammate_availability is a team-level feature, so
        # the two cannot be told apart from the data.
        return {'team': team, 'state': 'INJURY_REPORT_NOT_YET_FILED',
                'reason': f'no injuries row for {team} in any capture for '
                          f'{season} week {week}. This is ABSENCE OF A REPORT '
                          f'and is never read as absence of injury.',
                'n_rows': 0, 'newest_capture': None}
    got = _parse_ts(d['newest_capture'])
    ko = _parse_ts(kickoff_utc)
    wr = _parse_ts(written_at)
    if (ko and got and got >= ko) or (wr and got and got > wr):
        return {'team': team, 'state': 'INJURY_REPORT_CHRONOLOGY_FAILURE',
                'reason': f'the capture carrying {team}\'s rows was retrieved '
                          f'at {d["newest_capture"]}, which is not strictly '
                          f'before kickoff {kickoff_utc} / written_at '
                          f'{written_at}',
                **d}
    newest = _parse_ts(newest_overall)
    if got and newest and (newest - got).total_seconds() > STALE_HOURS * 3600:
        return {'team': team, 'state': 'INJURY_REPORT_STALE',
                'reason': f'the feed was refreshed at {newest_overall} but '
                          f'{team}\'s block has not changed since '
                          f'{d["newest_capture"]}, more than {STALE_HOURS:g}h '
                          f'earlier',
                **d}
    pop = d['population']
    if NEEDS_REPORT_STATUS and pop['report_status'] == 0:
        return {'team': team, 'state': 'INJURY_REPORT_INCOMPLETE',
                'reason': f'{team} has {d["n_rows"]} row(s) but report_status '
                          f'is unfilled on every one. teammate_availability '
                          f'reads it, and an unfiled designation is not an '
                          f'absence of injury.',
                **d}
    complete = all(pop[c] == d['n_rows'] for c in
                   ('report_status', 'practice_status'))
    return {'team': team,
            'state': 'READY_WITH_COMPLETE_INPUT' if complete else 'READY',
            'reason': 'the team satisfies the frozen input contract',
            **d}


def game_readiness(season: int = 2026, week: int = 1, games=None) -> dict:
    """Per-game execution readiness. A game is ready only if BOTH teams are.

    Each game is judged on its OWN two teams. A missing report elsewhere on the
    slate changes nothing here, and the suite checks that.
    """
    from nfl.capture import coverage as C
    if games is None:
        p = C.load_week_plan(season, week)
        if p.state.name != 'PASS':
            return {'artifact': 'NONQB_GAME_READINESS', 'season': season,
                    'week': week, 'fatal': f'{p.code}: {p.detail}',
                    'games': []}
        games = sorted({c.game_id: c.kickoff_utc for c in p.value}.items())
    out, counts = [], collections.Counter()
    for gid, ko in games:
        away, home = gid.split('_')[2:4]
        ko_s = (ko.isoformat().replace('+00:00', 'Z')
                if hasattr(ko, 'isoformat') else ko)
        tr = [team_readiness(season, week, t, kickoff_utc=ko_s)
              for t in (away, home)]
        worst = min(tr, key=lambda d: _SEVERITY[d['state']])
        ready = all(t['state'].startswith('READY') for t in tr)
        state = (('READY_WITH_COMPLETE_INPUT'
                  if all(t['state'] == 'READY_WITH_COMPLETE_INPUT' for t in tr)
                  else 'READY') if ready else worst['state'])
        counts[state] += 1
        out.append({'game_id': gid, 'kickoff_utc': ko_s, 'state': state,
                    'may_execute_d2': ready,
                    'blocking_team': None if ready else worst['team'],
                    'reason': ('both teams satisfy the frozen input contract'
                               if ready else worst['reason']),
                    'teams': tr})
    return {'artifact': 'NONQB_GAME_READINESS', 'season': season, 'week': week,
            'n_games': len(out),
            'n_executable': sum(1 for g in out if g['may_execute_d2']),
            'state_counts': dict(counts),
            'stale_hours': STALE_HOURS,
            'states_defined': list(GAME_STATES),
            'note': 'a game is judged on its own two teams only; a missing '
                    'report elsewhere on the slate does not change it, and a '
                    'missing report for a team is never read as that team '
                    'having no injuries',
            'games': out}


# =====================================================================
# R4 section M: the two future requirements are DIFFERENT and are named
# separately. Collapsing them into one "waiting on data" line is how a week-2
# forecast quietly runs on 2025 as though it were last week.
# =====================================================================
FUTURE_REQUIREMENTS = {
    'injuries_{season}': {
        'needed_from': 'WEEK 1',
        'serves': ['appearance (practice_progression, teammate_availability)'],
        'refusal_if_absent': 'INJURY_REPORT_NOT_YET_FILED / '
                             'INJURY_REPORT_INCOMPLETE, per game',
        'substitute': 'NONE. A reduced-feature fit would be a different model '
                      'wearing an accepted model name.',
    },
    'pbp_participation_{season}': {
        'needed_from': 'WEEK 2',
        'serves': ['participation (Stage-2 ewma_hl2 over prior pass-snap '
                   'shares)',
                   'targets_carries (the point forecast C is a prior share)',
                   'team_environment (team_dropbacks_part is a P4B metric)'],
        'refusal_if_absent': 'PARTICIPATION_HISTORY_STALE',
        'substitute': 'NONE. snap_counts is registered but carries no pass/run '
                      'split, so it cannot bound pass-play participation.',
        'why_week_1_is_safe': 'a week-1 forecast conditions only on PRIOR '
                              'seasons; panel_p3 carries 2020-2025.',
    },
}


def future_requirements(season: int = 2026, week: int = 1) -> dict:
    """What is needed, when, and what happens if it does not arrive.

    Both are reported at every week so neither can be forgotten because the
    other is the live one.
    """
    from nfl.production.nonqb import participation_prior as PP
    out = {}
    for tmpl, spec in FUTURE_REQUIREMENTS.items():
        name = tmpl.format(season=season)
        d = dict(spec)
        d['source'] = name
        if tmpl.startswith('injuries'):
            gr = game_readiness(season, week)
            d['state'] = ('SATISFIED' if gr.get('n_executable') == gr.get('n_games')
                          and gr.get('n_games') else 'NOT_SATISFIED')
            d['detail'] = (f"{gr.get('n_executable', 0)} of "
                           f"{gr.get('n_games', 0)} games executable")
        else:
            o = PP.share_prior(season, week,
                               [{'gsis_id': '_probe', 'position': 'WR'}])
            d['state'] = ('SATISFIED' if o.state.name == 'PASS'
                          else 'NOT_SATISFIED')
            d['detail'] = f'{o.state.value}[{o.code}]'
            d['newest_history_ordinal'] = (
                o.evidence.get('newest_history_ordinal')
                or o.evidence.get('newest_ordinal'))
            d['binds_at_week'] = 2
            d['binding_now'] = week >= 2
        out[name] = d
    return {'artifact': 'NONQB_FUTURE_REQUIREMENTS', 'season': season,
            'week': week, 'requirements': out,
            'note': 'two separate sources with two separate refusals. Week 2 '
                    'may not silently use 2025 as though it were last week.'}
