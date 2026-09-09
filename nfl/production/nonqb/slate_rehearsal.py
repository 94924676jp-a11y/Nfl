"""L: the REAL 2026 week-1 slate, on legitimate inputs only. No fixture.

This is the counterpart to `engine_rehearsal`. That one proves the wiring
works by feeding the chain a marked TEST-ONLY fixture. This one feeds it
nothing but what the capture path actually holds today, and records exactly
where the chain stops and why.

A stop here is the CORRECT result while the appearance source is unusable. It
is reported as a named DEFERRED/BLOCKED state per layer, never as a failure of
the engine and never as an empty forecast.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State                  # noqa: E402
from nfl.production import authorization as AUTH                     # noqa: E402
from nfl.production.rehearsal import run_slate as RS                 # noqa: E402
from nfl.production.nonqb import accounting as ACC                   # noqa: E402
from nfl.production.nonqb import layers as LY                        # noqa: E402
from nfl.production.nonqb import readiness as RD                     # noqa: E402

# The layers whose production role is gated on the appearance input.
CHAIN = ('appearance', 'participation', 'targets_carries',
         'receiving_conversion', 'td_layer')


def nonqb_chain(season, week, players):
    """Run D2-D5 with fixture=None. Every stop is named."""
    out = collections.OrderedDict()
    ap = LY.appearance(season, week, players, fixture=None)
    out['appearance'] = ap
    pa = LY.participation(ap, {})
    out['participation'] = pa
    tc = LY.targets_carries(pa, 'targets', [], [], ([], []), [], {})
    out['targets_carries'] = tc
    cv = LY.receiving_conversion(tc, [], {})
    out['receiving_conversion'] = cv
    td = LY.td_layer(cv, [], {})
    out['td_layer'] = td
    return out


def build(season=2026, week=1, out_dir='/tmp/v1r3-slate',
          written_at='2026-09-08T23:00:00Z'):
    slate = RS.build(season, week, out_dir, written_at)
    if 'fatal' in slate:
        return {'fatal': slate['fatal']}
    rd = RD.report(season, week)
    _, rrows = RS.roster(season, week)
    by_team = collections.defaultdict(list)
    for r in rrows:
        by_team[r['team']].append(r)

    games = []
    for g in slate['results']:
        away, home = g['game_id'].split('_')[2:4]
        players = [{'gsis_id': r['gsis_id'], 'position': r['position'],
                    'team': r['team']}
                   for t in (away, home) for r in by_team.get(t, [])]
        ch = nonqb_chain(season, week, players)
        chain = ACC.reconcile_chain(
            _stage(slate, g, 'team_environment'), ch['appearance'],
            ch['participation'], ch['targets_carries'],
            ch['receiving_conversion'], ch['td_layer'])
        games.append({
            'game_id': g['game_id'], 'status': g['status'],
            'n_players': g['n_players'],
            'qb_layer': _code(slate, g, 'qb_layer'),
            'team_environment': _code(slate, g, 'team_environment'),
            'nonqb': {k: f'{v.state.value}[{v.code}]' for k, v in ch.items()},
            'nonqb_accounting': f'{chain.state.value}[{chain.code}]',
            'publication': g['publication'],
        })

    pub = AUTH.may_publish()
    dist = collections.Counter()
    for g in games:
        for k, v in g['nonqb'].items():
            dist[(k, v)] += 1
    return {
        'artifact': 'NFL_V1_R3_REAL_SLATE_REHEARSAL',
        'TEST_ONLY': False,
        'fixtures_used': 'NONE -- every non-QB layer was called with '
                         'fixture=None',
        'season': season, 'week': week, 'n_games': len(games),
        'written_at': written_at,
        'roster_source': slate['roster_source'],
        'n_roster_rows': slate['n_roster_rows'],
        'readiness_state': rd['overall_state'],
        'readiness_next_action': rd['next_action'],
        'injuries': rd['injuries'],
        'games': games,
        'layer_state_distribution': {f'{k}: {v}': n
                                     for (k, v), n in sorted(dist.items())},
        'publication': f'{pub.state.value}[{pub.code}]',
        'gates': rd['gates'],
    }


def _stage(slate, g, name):
    """The production entrypoint's own outcome for a stage, as an Outcome-ish
    object. It is read from the run summary, never recomputed here."""
    from sportsplatform.governance.outcome import Outcome
    code = _code(slate, g, name)
    st, c = (code.split('[', 1)[0], code.split('[', 1)[1].rstrip(']')) \
        if '[' in code else ('UNKNOWN', code)
    if st == 'PASS':
        return Outcome.ok(c, value=True)
    return Outcome.not_applicable(c, f'{name} reported {code}')


def _code(slate, g, name):
    """The stage's own reported state. NEVER inferred from absence."""
    for st in g.get('stages', ()):
        if st['stage'] == name:
            return f"{st['state']}[{st['code']}]"
    return 'ABSENT[STAGE_NOT_REPORTED]'


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--season', type=int, default=2026)
    ap.add_argument('--week', type=int, default=1)
    ap.add_argument('--out-dir', default='/tmp/v1r3-slate')
    ap.add_argument('--written-at', default='2026-09-08T23:00:00Z')
    a = ap.parse_args()
    r = build(a.season, a.week, a.out_dir, a.written_at)
    if 'fatal' in r:
        print('FATAL', r['fatal']); sys.exit(1)
    json.dump(r, open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   'slate_rehearsal.json'), 'w'), indent=1,
              default=str)
    print(json.dumps({k: v for k, v in r.items() if k != 'games'}, indent=1,
                     default=str))
    print(f"\n{r['n_games']} games; per-game non-QB states are identical by "
          f"construction (the blocking condition is slate-level).")
    print('wrote slate_rehearsal.json')
