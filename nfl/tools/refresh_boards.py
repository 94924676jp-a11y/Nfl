"""Scheduled entry point for the pregame board refresh.

    python3.12 nfl/tools/refresh_boards.py --game-id 2026_01_SF_LA
    python3.12 nfl/tools/refresh_boards.py --week 1 --all-upcoming

Idempotent. Running it more often produces no more boards -- a new board is
written only when the stored input vintages actually change. Exit code is 0
whenever the pass completed, INCLUDING when it deliberately wrote nothing;
a scheduler must not read `no new inputs` as a failure.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.product import orchestrator as ORC                      # noqa: E402
from nfl.product import store as ST                              # noqa: E402


def upcoming(season, week):
    from nfl.capture import coverage as C
    p = C.load_week_plan(season, week)
    if p.state.name != 'PASS':
        raise SystemExit(f'WEEK_PLAN_UNAVAILABLE: {p.code}')
    now = dt.datetime.now(dt.timezone.utc)
    out = {}
    for c in p.value:
        ko = c.kickoff_utc
        if ko and ko > now:
            out[c.game_id] = ko
    return sorted(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--game-id', action='append', default=[])
    ap.add_argument('--season', type=int, default=2026)
    ap.add_argument('--week', type=int, default=1)
    ap.add_argument('--all-upcoming', action='store_true')
    ap.add_argument('--draws', type=int, default=1000)
    ap.add_argument('--seed', type=int, default=20260908)
    ap.add_argument('--model-configuration', default='V1_CANDIDATE')
    ap.add_argument('--plan-only', action='store_true',
                    help='report what a run would do and write nothing')
    a = ap.parse_args()

    games = list(a.game_id)
    if a.all_upcoming:
        games += [g for g in upcoming(a.season, a.week) if g not in games]
    if not games:
        raise SystemExit('NO_GAME_SELECTED: pass --game-id or --all-upcoming')

    if a.plan_only:
        for g in games:
            p = ORC.plan(g, a.season, a.week)
            p.pop('information_set', None)
            print(json.dumps(p, sort_keys=True, default=str))
        return 0

    res = ORC.run(games, season=a.season, week=a.week, draws=a.draws,
                  seed=a.seed, model_configuration=a.model_configuration)
    for r in res:
        line = f'{r["game_id"]:<18} {r["status"]}'
        if r['status'] == 'WRITTEN':
            line += (f'  run {r["run_id"]}  {r["label"]}  '
                     f'-> {r["board_dir"]}')
        elif r['status'] == 'NO_NEW_INPUTS':
            line += f'  (unchanged since {r.get("previous_written_at")})'
        elif r['status'] in ('REFUSED', 'ERROR'):
            line += f'  {r.get("refusal") or r.get("error")}'
        print(line)
    n = sum(1 for r in res if r['status'] == 'WRITTEN')
    print(f'-- {n} board(s) written, {len(res)} game(s) checked')
    # A PASS THAT WROTE NOTHING IS A SUCCESSFUL PASS.
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
