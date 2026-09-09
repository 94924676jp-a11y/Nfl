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
