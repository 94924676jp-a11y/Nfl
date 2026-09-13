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



def _inactive_provenance(game_id, teams, inactive_ids):
    """What the ownership verdict is allowed to judge itself on.

    Read from the governed ingestion record written by
    `nfl/tools/ingest_inactives.py`, never assembled from the caller's
    intentions. Absent the record there is no provenance and the verdict
    fails closed -- which is the correct reading of a board sealed before any
    list was consumed.
    """
    if not inactive_ids:
        return None
    rec = _REPO / 'nfl' / 'research' / 'live' / game_id / 'INACTIVES_INGESTION.json'
    if not rec.exists():
        return {'game_id': game_id, 'teams': list(teams),
                'post_inactives_complete': False,
                'n_unmapped': None,
                'why': 'no INACTIVES_INGESTION.json for this game'}
    try:
        d = json.loads(rec.read_text())
    except (ValueError, OSError):
        return {'game_id': game_id, 'teams': list(teams),
                'post_inactives_complete': False, 'n_unmapped': None,
                'why': 'the ingestion record could not be read'}
    steps = {s['step'][:3].strip(): s for s in (d.get('steps') or [])}
    ident, complete = steps.get('3.'), steps.get('4.')
    # THE RECORD MUST DESCRIBE *THIS* INACTIVE SET, NOT A PREVIOUS ONE.
    #
    # `INACTIVES_INGESTION.json` is written by a tool that also seals these
    # boards, so a run reads whatever the PREVIOUS run left behind unless the
    # record is checkpointed first. On a first ingestion that is no file at
    # all; on a re-ingestion it is a record of different bytes, which is the
    # worse failure because it looks populated. Tie it to the set being sealed
    # and fail closed on any mismatch rather than describing the wrong list.
    by_team = (complete or {}).get('inactive_by_team') or {}
    in_rec = {p for v in by_team.values() for p in (v or [])}
    if in_rec != set(inactive_ids or ()):
        return {'game_id': game_id, 'teams': list(teams),
                'post_inactives_complete': False, 'n_unmapped': None,
                'why': 'INACTIVES_INGESTION_RECORD_DOES_NOT_DESCRIBE_THIS_SET: '
                       f'the record lists {len(in_rec)} inactive player(s) and '
                       f'this seal carries {len(set(inactive_ids or ()))}. A '
                       f'record of a different ingestion is not provenance for '
                       f'this one.',
                'record': str(rec.relative_to(_REPO))}
    return {
        'game_id': game_id,
        'teams': list(teams),
        'post_inactives_complete': bool(complete and complete.get('ok')),
        'n_unmapped': (ident or {}).get('n_unmapped'),
        'unmapped': (ident or {}).get('unmapped'),
        # Per-name detail when the ingestion recorded it. Absent, every
        # unresolved name is UNKNOWN_POSITION and QB enforcement fails closed.
        'unmapped_detail': ((ident or {}).get('unmapped_detail')
                            or d.get('unmapped_detail')),
        'segmentation': d.get('segmentation'),
        'provenance_kind': (d.get('provenance') or {}).get('kind'),
        'record': str(rec.relative_to(_REPO)),
    }


def build_one(season, week, game_id, written_at, out_dir, draws=1000,
              seed=20260908, model_configuration='V1_CANDIDATE',
              inactive_ids=None):
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

    # THE OFFICIAL INACTIVE SET, IF ONE HAS BEEN ESTABLISHED. Absent, this is
    # None and the run is a pre-inactives board -- which is what every board
    # sealed before the list publishes must remain.
    fx = {'kickoff_utc': ko,
          'official_inactive_ids': list(inactive_ids or []) or None,
          'official_inactive_provenance': _inactive_provenance(
              game_id, teams, inactive_ids),
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
    # THE GOVERNED OWNERSHIP STATE, CARRIED NOT RE-DERIVED. The product board
    # reads `qb_inactive_ownership_enforced` to decide whether
    # QB_INACTIVE_NOT_CONSUMED still applies. Until 2026-09-13 nothing in the
    # repository wrote it, so the flag could never clear even on a board that
    # had demonstrably consumed the official list. It now comes from the
    # allocation layer that actually enforced it, through run_status.
    bd['qb_inactive_ownership'] = summary.get('qb_inactive_ownership')
    bd['qb_inactive_ownership_enforced'] = bool(
        summary.get('qb_inactive_ownership_enforced'))

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
