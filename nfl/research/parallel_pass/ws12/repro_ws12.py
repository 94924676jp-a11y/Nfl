#!/usr/bin/env python3.12
"""WS12 reproductions. READ-ONLY: this script imports repository modules and
reads committed artifacts. It writes nothing and changes nothing.

    python3.12 nfl/research/parallel_pass/ws12/repro_ws12.py

Three reproductions, each printing the numbers quoted in
WS12_TEMPORAL_LEAKAGE.md.

  L1  layers.appearance selects the injuries feed with NO clock.
  L2  layers.appearance gates readiness on kickoff, never on written_at.
  L3  board.depth_rank selects a depth vintage by glob order, with no clock.
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[4]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.capture import coverage as C                     # noqa: E402
from nfl.product import board as B                        # noqa: E402
from nfl.production.nonqb import readiness as RD          # noqa: E402


def P(t):
    d = dt.datetime.fromisoformat(str(t).replace('Z', '+00:00'))
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def _read(p):
    txt = (gzip.open(p, 'rt').read() if str(p).endswith('.gz')
           else open(p).read())
    return list(csv.DictReader(txt.splitlines()))


def _sig(rows):
    return {r['gsis_id']: (r.get('report_status'), r.get('practice_status'))
            for r in rows}


def _team_rows(rows, team, season=2026, week=1):
    return [r for r in rows if r.get('season') == str(season)
            and r.get('week') == str(week) and r.get('team') == team]


def kickoffs(season=2026, week=1):
    plan = C.load_week_plan(season, week)
    if plan.state.name != 'PASS':
        raise SystemExit(f'WEEK_PLAN_UNAVAILABLE: {plan.code}')
    out = {}
    for c in plan.value:
        a, h = c.game_id.split('_')[2:4]
        out[a] = out[h] = (c.game_id, c.kickoff_utc)
    return out


def l1_unbounded_injuries_feed():
    print('=' * 72)
    print('L1  nfl/production/nonqb/layers.py:145 -> readiness.py:36/62')
    print('=' * 72)
    ts, rows = RD._latest_injuries(2026)
    ko = kickoffs()
    later = sum(1 for _, (_, k) in ko.items() if P(ts) >= P(k))
    games = {g for g, _ in ko.values()}
    print(f'  latest_injuries_rows(2026) retrieved_at = {ts}')
    print(f'  rows returned                           = {len(rows)}')
    print(f'  teams whose kickoff it is AT OR AFTER   = {later} of {len(ko)}'
          f'  ({len(games)} week-1 games)')
    print('  the selector applies no as_of, no written_at and no kickoff '
          'bound.')
    # NE/SEA: the capture consumed post-kickoff differs in content.
    for team in ('NE', 'SEA'):
        gid, k = ko[team]
        cut = P(k) - dt.timedelta(microseconds=1)
        elig = RD._all_injury_captures(2026, as_of=cut)
        pre = _sig(_team_rows(_read(elig[0][1]), team))
        lat = _sig(_team_rows(rows, team))
        d = [x for x in set(pre) | set(lat) if pre.get(x) != lat.get(x)]
        print(f'  {team} ({gid}, kickoff {k}): pre-kickoff vintage '
              f'{elig[0][0]}')
        print(f'     player rows whose designation differs from the vintage '
              f'actually consumed: {len(d)}')
        for x in sorted(d)[:4]:
            print(f'       {x}  pre={pre.get(x)}  consumed={lat.get(x)}')


def l2_written_at_gap():
    print()
    print('=' * 72)
    print('L2  nfl/production/nonqb/layers.py:117 -- written_at not passed')
    print('=' * 72)
    ko = kickoffs()
    gr = RD.game_readiness(2026, 1)
    ready_games = {g['game_id'] for g in gr['games'] if g['may_execute_d2']}
    ready_teams = sorted({t for t, (g, _) in ko.items() if g in ready_games})
    print(f'  games passing the readiness gate today: {len(ready_games)} of '
          f'{gr["n_games"]}')
    total = 0
    for team in ready_teams:
        gid, k = ko[team]
        wa = P(k) - dt.timedelta(hours=24)     # a plausible written_at
        e_wa = RD._all_injury_captures(2026, as_of=wa)
        e_ko = RD._all_injury_captures(
            2026, as_of=P(k) - dt.timedelta(microseconds=1))
        if not e_wa or not e_ko:
            continue
        a = _sig(_team_rows(_read(e_wa[0][1]), team))
        b = _sig(_team_rows(_read(e_ko[0][1]), team))
        d = [x for x in set(a) | set(b) if a.get(x) != b.get(x)]
        total += len(d)
        if d:
            print(f'  {team:4s} {gid:16s} T-24h={e_wa[0][0][:19]}  '
                  f'kickoff-cut={e_ko[0][0][:19]}  differ={len(d)}')
    print(f'  TOTAL player rows differing between a T-24h written_at and the '
          f'kickoff cut: {total}')
    print('  every one of them is admitted by the gate the appearance layer '
          'actually calls.')


def l3_depth_rank_glob_order():
    print()
    print('=' * 72)
    print('L3  nfl/product/board.py:55 <- nfl/production/run_forecast.py:681')
    print('=' * 72)
    teams = ('SF', 'LA')
    paths = sorted((_REPO / 'nfl' / 'vintage').glob(
        'depth_charts.*.reduced.csv.gz'))
    print('  glob order (content-hash order, not time order):')
    last = None
    for p in paths:
        rows = [r for r in csv.DictReader(gzip.open(p, 'rt'))
                if r.get('team') in teams and r.get('gsis_id')]
        mx = max((r['dt'] for r in rows), default=None)
        print(f'    {p.name}  rows={len(rows):4d}  max dt={mx}')
        if rows:
            last = (p.name, mx)
    got = B.depth_rank(2026, 1, teams)
    print(f'  depth_rank(2026, 1, {teams}) returns {len(got)} players')
    print(f'  effective vintage = {last[0]} at dt {last[1]}')
    print('  it is neither the newest chart nor a point-in-time one; it is '
          'the last blob in filename order that carries rows for these teams.')
    print('  depth_rank takes no clock argument at all.')


if __name__ == '__main__':
    l1_unbounded_injuries_feed()
    l2_written_at_gap()
    l3_depth_rank_glob_order()
