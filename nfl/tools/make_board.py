"""Produce a chronology-valid sealed forecast for one game, and its board.

    python3.12 nfl/tools/make_board.py --game-id 2026_01_SF_LA \
        --written-at 2026-09-10T16:00:00Z --out-dir /path

THE FORECAST IS SEALED BEFORE THE BOARD IS RENDERED, and the board records the
run id, draw hash, component manifest, input vintages and authorization state
of the exact artifact it read. A board that cannot name the forecast it came
from is a screenshot, not a record.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import hashlib
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production import run_forecast as RUN                    # noqa: E402
from nfl.production.nonqb import readiness as RD                  # noqa: E402
from nfl.product import board as B                                # noqa: E402
from nfl.product import names as NM                               # noqa: E402
from nfl.product import render as R                               # noqa: E402
from nfl.research.shadow import information_set as IS             # noqa: E402


def kickoff_for(season, week, game_id):
    from nfl.capture import coverage as C
    p = C.load_week_plan(season, week)
    if p.state.name != 'PASS':
        raise SystemExit(f'WEEK_PLAN_UNAVAILABLE: {p.code}')
    for c in p.value:
        if c.game_id == game_id:
            k = c.kickoff_utc
            return (k.isoformat().replace('+00:00', 'Z')
                    if hasattr(k, 'isoformat') else k)
    raise SystemExit(f'GAME_NOT_IN_WEEK_PLAN: {game_id}')


def build_one(season, week, game_id, written_at, out_dir, draws=1000,
              seed=20260908, model_configuration='V1_CANDIDATE'):
    """Seal a forecast and render its board. Returns (summary, board, dir)."""
    away, home = game_id.split('_')[2:4]
    teams = (away, home)
    ko = kickoff_for(season, week, game_id)

    wrote = dt.datetime.fromisoformat(written_at.replace('Z', '+00:00'))
    kick = dt.datetime.fromisoformat(ko.replace('Z', '+00:00'))
    if not wrote < kick:
        raise SystemExit(
            f'WRITTEN_AT_NOT_BEFORE_KICKOFF: {written_at} >= {ko}. A pregame '
            f'board cannot be built from a post-kickoff clock.')
    # A WRITTEN_AT IN THE FUTURE IS NEVER RIGHT, AND NOTHING CHECKED IT.
    #
    # Every other clock in this function was guarded -- written_at against
    # kickoff, each source against written_at -- and the one clock nobody
    # compared to the wall was written_at itself. Measured 2026-09-10T21:19:30Z:
    # a tournament was sealed claiming written_at 21:30:00Z, eleven minutes
    # ahead. Nothing objected, and the artifact asserted a provenance that had
    # not happened yet. Worse, a future cutoff silently WIDENS the information
    # set: any capture landing between now and it would be admitted as though
    # it had been available at write time.
    now = dt.datetime.now(dt.timezone.utc)
    if wrote > now:
        raise SystemExit(
            f'WRITTEN_AT_IN_THE_FUTURE: {written_at} is after the current '
            f'clock {now.isoformat().replace("+00:00", "Z")}. A forecast '
            f'cannot have been written at a time that has not happened, and a '
            f'cutoff ahead of now would admit captures that do not exist yet.')

    # SELECT AGAINST THE CLOCK THE FORECAST CONSUMES, then verify. The check
    # below is kept -- it is now a proof that selection did its job rather than
    # a refusal triggered by an ordinary newer capture.
    info = IS.build(ko, observed_before=written_at)
    for name, rec in info['sources'].items():
        if rec['observed_at'] >= written_at:
            raise SystemExit(
                f'SOURCE_AFTER_WRITTEN_AT: {name} at {rec["observed_at"]}')

    roster_blob = info['sources']['weekly_rosters']['blob']
    depth_blob = info['sources']['depth_charts']['blob']
    rows = [r for r in csv.DictReader(gzip.open(_REPO / roster_blob, 'rt'))
            if r['season'] == str(season) and r['week'] == str(week)
            and r['team'] in teams]
    if not rows:
        raise SystemExit(f'ROSTER_EMPTY for {teams}')
    players = [{'gsis_id': r['gsis_id'], 'position': r['position'],
                'team': r['team']} for r in rows]

    fx = {'kickoff_utc': ko,
          'source_hashes': {k: {'sha256': v['sha256'],
                                'retrieved_at': v['observed_at']}
                            for k, v in info['sources'].items()},
          'players': players, 'team_ids': [away, home],
          'qb_slate': {'prospective': True}, 'qb_draws': draws,
          'team_volume': True, 'distributions': {}}
    args = argparse.Namespace(
        season=season, week=week, game_id=game_id, arm='A',
        written_at=written_at, out_dir=out_dir, seed=seed,
        dry_run=True, fixtures=None,
        model_configuration=model_configuration)

    summary = RUN.build(args, fx)
    run_dir = pathlib.Path(out_dir) / summary['run_id']
    if summary['status'] != 'SEALED':
        return summary, None, run_dir

    RD.cache_clear()
    ready = {t: RD.team_readiness(season, week, t, kickoff_utc=ko,
                                 written_at=written_at) for t in teams}
    bd = B.build(run_dir, season, week, readiness_by_team=ready,
                 roster_blob=roster_blob, depth_blob=depth_blob)
    bd['information_set'] = info
    bd['pipeline_status'] = summary['status']

    (run_dir / 'board.json').write_text(
        json.dumps(bd, indent=1, sort_keys=True, default=str))
    # Names resolved under the SAME cut as the forecast. Display only.
    NM.cache_clear()
    md = R.render(bd, names=NM.lookup(written_at))
    (run_dir / 'BOARD.md').write_text(md)
    (run_dir / 'BOARD_SHA256.txt').write_text(
        f'{hashlib.sha256(md.encode()).hexdigest()}  BOARD.md\n')
    return summary, bd, run_dir


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--game-id', required=True)
    ap.add_argument('--season', type=int, default=2026)
    ap.add_argument('--week', type=int, default=1)
    ap.add_argument('--written-at', required=True,
                    help='REQUIRED. There is no wall-clock default for a '
                         'scientific clock.')
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--draws', type=int, default=1000)
    ap.add_argument('--seed', type=int, default=20260908)
    ap.add_argument('--model-configuration', default='V1_CANDIDATE')
    a = ap.parse_args()

    summary, bd, run_dir = build_one(
        a.season, a.week, a.game_id, a.written_at, a.out_dir, a.draws,
        a.seed, a.model_configuration)
    print('status', summary['status'], 'run_id', summary['run_id'])
    for st in summary['stages']:
        print('  %-22s %-16s %s' % (st['stage'], st['state'],
                                    st.get('code') or ''))
    if bd is None:
        return 3
    print('board  ', run_dir / 'BOARD.md')
    print('players', bd['n_players'], '| authorization',
          bd['authorization']['label'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
