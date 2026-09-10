"""Run the FROZEN V1 candidate against a strictly pre-kickoff information set.

SHADOW EVALUATION ONLY. Nothing here is promoted, nothing here is prospective
evidence, and nothing here modifies V1: the forecasting architecture is called
through its own canonical entrypoint (`nfl.production.run_forecast.build`) with
no argument that does not already exist.

ORDER OF OPERATIONS IS THE POINT

The forecast is produced and SEALED -- written to disk and hashed -- before any
outcome file is opened. This module has no import of, and no path to, an
outcome source. Scoring lives in a separate module that takes the sealed
artifact's hash as an argument and refuses to run without it.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production import run_forecast as RUN            # noqa: E402
from nfl.research.shadow import information_set as IS      # noqa: E402

# --- DECLARED BEFORE ANY OUTCOME WAS OPENED -------------------------------
# Every one of these is an execution choice, not a fitted quantity. They are
# named here so that a reader can see they were fixed in advance rather than
# selected to make a score look better.
DECLARED = {
    'game_id': '2026_01_NE_SEA',
    'season': 2026,
    'week': 1,
    'kickoff_utc': '2026-09-10T00:20:00Z',
    # After the newest legitimate pre-kickoff capture (2026-09-08T17:06:03Z)
    # and 31.2 hours before kickoff. NOT chosen to clear a guard: it is the
    # earliest instant at which the whole pre-kickoff information set exists.
    'written_at': '2026-09-08T17:10:00Z',
    'arm': 'A',
    'model_configuration': 'V1_CANDIDATE',
    # The seed the canonical rehearsal slate already used. Reusing it removes
    # any suspicion that a seed was searched over.
    'seed': 20260908,
    # MONTE CARLO RESOLUTION ONLY -- not a model parameter. The rehearsal ran
    # 200 draws, which cannot support a percentile, a CRPS or a PIT value
    # worth reporting.
    #
    # 1000 IS A CAPABILITY CEILING, NOT A PREFERENCE, AND IT WAS DISCOVERED
    # BEFORE ANY OUTCOME FILE WAS OPENED. The first attempt declared 4000 and
    # the run REFUSED at player_draws with DRAW_INDEX_RAGGED: team_volume
    # delivered 1000 draws against the run's 4000. Cause, read out of the
    # code rather than guessed -- `team_volume_v1.forecast` ends with
    # `V.draw(...)[:, :m]`, and `p4b_volume.draw` always returns exactly
    # `p4b_volume.M_DRAWS = 1000` columns. The `m` argument can therefore only
    # ever TRUNCATE; it cannot resize. Asking for more than 1000 silently
    # yields 1000 everywhere the slice is not checked. See
    # POST_V1_REFINEMENT `TEAM_VOLUME_DRAW_COUNT_TRUNCATES_SILENTLY`.
    #
    # This is left UNFIXED: V1 is frozen and the owner's instruction for this
    # task is not to modify it. The replay runs at the count the engine can
    # actually deliver, and says so.
    'draws': 1000,
    'draws_note': 'ceiling imposed by p4b_volume.M_DRAWS; the first declared '
                  'value of 4000 was refused by the B13 draw-index guard '
                  'before any outcome was opened',
}


def _roster(blob: pathlib.Path, season, week, teams):
    rows = [r for r in csv.DictReader(gzip.open(blob, 'rt'))
            if r['season'] == str(season) and r['week'] == str(week)
            and r['team'] in teams]
    if not rows:
        raise IS.InformationSetError(
            f'ROSTER_EMPTY: {blob.name} yielded no {season} week {week} rows '
            f'for {sorted(teams)}')
    return [{'gsis_id': r['gsis_id'], 'position': r['position'],
             'team': r['team']} for r in rows]


def depth_chart(blob: pathlib.Path, teams):
    """The newest pre-kickoff depth chart, as {(team, pos, rank): gsis_id}."""
    rows = [r for r in csv.DictReader(gzip.open(blob, 'rt'))
            if r.get('team') in teams and r.get('gsis_id')]
    if not rows:
        raise IS.InformationSetError(
            f'DEPTH_CHART_EMPTY: {blob.name} yielded no rows for '
            f'{sorted(teams)}')
    newest = max(r['dt'] for r in rows)
    out = {}
    for r in rows:
        if r['dt'] != newest:
            continue
        try:
            rank = int(r['pos_rank'])
        except (TypeError, ValueError):
            continue
        out[(r['team'], r['pos_abb'], rank)] = r['gsis_id']
    return {'as_of': newest, 'chart': out}


def run(out_dir: pathlib.Path) -> dict:
    d = DECLARED
    away, home = d['game_id'].split('_')[2], d['game_id'].split('_')[3]
    teams = (away, home)

    info = IS.build(d['kickoff_utc'])
    for name, rec in info['sources'].items():
        if rec['observed_at'] >= d['written_at']:
            raise IS.InformationSetError(
                f'SOURCE_AFTER_WRITTEN_AT: {name} observed {rec["observed_at"]}'
                f' is not before written_at {d["written_at"]}')

    roster_blob = _REPO / info['sources']['weekly_rosters']['blob']
    players = _roster(roster_blob, d['season'], d['week'], teams)
    dc = depth_chart(_REPO / info['sources']['depth_charts']['blob'], teams)

    # The entrypoint validates every source hash and every retrieval time it is
    # given, so it is given the REAL ones rather than the rehearsal's
    # placeholder 'b'*64.
    source_hashes = {
        name: {'sha256': rec['sha256'], 'retrieved_at': rec['observed_at']}
        for name, rec in info['sources'].items()
    }

    fx = {'kickoff_utc': d['kickoff_utc'],
          'source_hashes': source_hashes,
          'players': players,
          'team_ids': [away, home],
          'qb_slate': {'prospective': True},
          'qb_draws': d['draws'],
          'team_volume': True,
          'distributions': {}}

    args = argparse.Namespace(
        season=d['season'], week=d['week'], game_id=d['game_id'],
        arm=d['arm'], written_at=d['written_at'], out_dir=str(out_dir),
        seed=d['seed'], dry_run=True, fixtures=None,
        model_configuration=d['model_configuration'])

    summary = RUN.build(args, fx)

    return {'declared': d, 'information_set': info, 'depth_chart': dc,
            'n_players': len(players), 'summary': summary}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--seal-to', required=True,
                    help='path for the sealed forecast bundle')
    a = ap.parse_args()

    res = run(pathlib.Path(a.out_dir))

    st = res['summary']['status']
    fails = [s for s in res['summary']['stages']
             if s['state'] not in ('PASS', 'NOT_APPLICABLE')]

    bundle = {
        'what': 'NE@SEA shadow replay of the frozen V1 candidate',
        'promoted': False,
        'prospective_eligible': False,
        'outcome_ingested': False,
        'declared': res['declared'],
        'information_set': res['information_set'],
        'depth_chart_as_of': res['depth_chart']['as_of'],
        'depth_chart': {f'{k[0]}|{k[1]}|{k[2]}': v
                        for k, v in sorted(res['depth_chart']['chart'].items())},
        'n_players': res['n_players'],
        'status': st,
        'failures': fails,
        'run': res['summary'],
    }
    p = pathlib.Path(a.seal_to)
    p.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(bundle, indent=1, sort_keys=True, default=str)
    p.write_text(body)
    print('SEALED', p)
    print('sha256', hashlib.sha256(body.encode()).hexdigest())
    print('status', st)
    for f in fails:
        print('  FAIL', f['stage'], f['code'])
    return 0 if st != 'REFUSED' else 3


if __name__ == '__main__':
    raise SystemExit(main())
