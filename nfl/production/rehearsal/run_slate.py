"""NFL-V1-R1: run the whole upcoming slate through the production entrypoint.

REHEARSAL ONLY. Every artifact this produces is tagged dry_run and
prospective_eligible=false, and publication stays refused while G0A is
incomplete. This does not forecast for money and cannot.
"""
from __future__ import annotations

import argparse
import collections
import csv
import glob
import gzip
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
for _q in (_ROOT, os.path.join(_ROOT, 'nfl', 'research', 'qb2'),
           os.path.join(_ROOT, 'nfl', 'research', 'rc1')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

from nfl.capture import coverage as C                             # noqa: E402
from nfl.production import fixture_assembler as FA                # noqa: E402
from nfl.production import run_forecast as RUN                    # noqa: E402
from sportsplatform.governance.outcome import State              # noqa: E402

# Failure taxonomy, per s.D. Every failure gets one of these; "error" is not a
# category.
CATS = ('DATA_MISSING', 'ID_RECONCILIATION', 'ACCOUNTING', 'MODEL_INTERFACE',
        'AUTHORIZATION', 'CHRONOLOGY', 'PRODUCTION_ENTRYPOINT', 'OTHER_NAMED')

CODE_CAT = {
    'QB_SLATE_EMPTY': 'MODEL_INTERFACE',
    'QB_FRAME_MISSING': 'DATA_MISSING',
    'STAGE_NOT_IMPLEMENTED': 'MODEL_INTERFACE',
    'MODEL_ARTIFACT_MISSING': 'DATA_MISSING',
    'MODEL_HASH_MISMATCH': 'DATA_MISSING',
    'IDENTITY_UNRESOLVED': 'ID_RECONCILIATION',
    'REQUIRED_GAME_MISSING': 'DATA_MISSING',
    'INCOMPLETE_PLAYER_ACCOUNTING': 'ACCOUNTING',
    'JOINT_RECONCILIATION_FAILURE': 'ACCOUNTING',
    'QB_DRAW_ACCOUNTING_VIOLATED': 'ACCOUNTING',
    'SOURCE_MISSING': 'DATA_MISSING',
    'REQUIRED_SOURCE_NOT_DECLARED': 'DATA_MISSING',
    'UNAUTHORIZED_INPUT': 'DATA_MISSING',
    'SOURCE_TOO_LATE': 'CHRONOLOGY',
    'SOURCE_CHRONOLOGY_FAILURE': 'CHRONOLOGY',
    'RAW_HASH_MISMATCH': 'DATA_MISSING',
    'SCHEMA_DRIFT': 'DATA_MISSING',
    'ARM_RULE_VIOLATION': 'CHRONOLOGY',
    'COLD_START_VIOLATION': 'CHRONOLOGY',
    'NFL1_NOT_AUTHORIZED': 'AUTHORIZATION',
    'ARTIFACT_SEALING_FAILURE': 'PRODUCTION_ENTRYPOINT',
    'STAGE_RAISED': 'PRODUCTION_ENTRYPOINT',
    'STAGE_NOT_REACHED': 'PRODUCTION_ENTRYPOINT',
}


def roster(season, week, written_at=None):
    """The player set for an UPCOMING week comes from the roster, not history.

    This is the whole point: a live forecast must be able to name players for a
    season that has not been played. Sourcing the player set from a historical
    panel can only ever 'forecast' the past.

    FIX-ROSTER-GLOB. THE VINTAGE IS SELECTED, NOT GUESSED. This function used
    to glob `nfl/vintage/weekly_rosters.*.reduced.csv.gz` and keep whichever
    file held the MOST ROWS. Row count, glob order, filename order, file size
    and filesystem mtime are the five inputs `vintage_selector.select` names
    as FORBIDDEN for choosing a vintage, and this used two of them. The file
    with the most rows is not the file that was lawful at the run cut: on a
    week where a later capture is larger, "most rows" and "lawful at the cut"
    pick different files and nothing says so.

    The roster now comes from `fixture_assembler.assemble_game`, which reads
    the blob the run DECLARES, selected by `vintage_selector` at the cut. A
    caller with no cut is REFUSED rather than silently handed a glob: there is
    no lawful vintage without an instant to be lawful at.
    """
    if not written_at:
        raise ValueError(
            'ROSTER_CUT_REQUIRED: a roster vintage cannot be chosen without '
            'a run cut. Pass written_at; do not fall back to a glob.')
    o = FA.assemble(written_at)
    if o.state is not State.PASS:
        raise ValueError(f'ROSTER_VINTAGE_UNAVAILABLE: {o.code}: {o.detail}')
    blob = (o.evidence or {})['detail_by_source']['weekly_rosters']['blob']
    with gzip.open(os.path.join(_ROOT, blob), 'rt') as fh:
        rows = [x for x in csv.DictReader(fh)
                if x['season'] == str(season) and x['week'] == str(week)]
    return os.path.basename(blob), rows


def build(season, week, out_dir, written_at,
          model_configuration=None):
    plan = C.load_week_plan(season, week)
    if plan.state.name != 'PASS':
        return {'fatal': f'{plan.code}: {plan.detail}'}
    games = sorted({c.game_id: c for c in plan.value}.items())
    ko = {c.game_id: c.kickoff_utc for c in plan.value}
    src_file, rrows = roster(season, week, written_at=written_at)
    by_team = collections.defaultdict(list)
    for r in rrows:
        by_team[r['team']].append(r)

    # ASSEMBLED ONCE FOR THE SLATE, at the run's own cut. Every game in a
    # slate is written at the same instant, so selecting the vintages once is
    # not a shortcut -- it is the statement that all sixteen games read the
    # same evidence, which is what makes them comparable.
    fixture_sources = FA.assemble(written_at)

    results = []
    for gid, _ in games:
        parts = gid.split('_')
        away, home = parts[2], parts[3]
        players = [{'gsis_id': r['gsis_id'], 'position': r['position'],
                    'team': r['team']}
                   for t in (away, home) for r in by_team.get(t, [])]
        # DK-4. THE PLACEHOLDER IS GONE. This used to read
        #     'source_hashes': {'schedules': {'sha256': 'b' * 64, ...}}
        # -- one source, a fabricated hash -- which is why this module was
        # declared REHEARSAL ONLY and why it still sets dry_run below. The
        # fixture is now assembled from the vintage manifest by
        # `fixture_assembler`, which selects each capture with the SAME call
        # the football layers make and hashes the blob bytes itself.
        #
        # `dry_run` is deliberately UNCHANGED here. Removing the placeholder
        # makes this driver honest about its inputs; it does not make a module
        # whose own docstring says REHEARSAL ONLY into the production path,
        # and promoting it by side effect of a data fix is not a decision this
        # commit gets to take quietly.
        if fixture_sources.state is not State.PASS:
            results.append({'game_id': gid, 'status': 'REFUSED',
                            'n_players': len(players),
                            'failures': [{'stage': 'fixture_assembly',
                                          'code': fixture_sources.code,
                                          'category': 'DATA_MISSING',
                                          'detail': (fixture_sources.detail
                                                     or '')[:200]}],
                            'stages': [], 'publication': None,
                            'run_id': None})
            continue
        fx = {'kickoff_utc': ko[gid].isoformat().replace('+00:00', 'Z'),
              'source_hashes': dict(fixture_sources.value),
              'players': players, 'team_ids': [away, home],
              'qb_slate': {'prospective': True}, 'qb_draws': 200,
              'team_volume': True,
              'distributions': {}}
        a = argparse.Namespace(season=season, week=week, game_id=gid, arm='A',
                               written_at=written_at, out_dir=out_dir,
                               seed=20260908, dry_run=True, fixtures=None,
                               model_configuration=model_configuration)
        s = RUN.build(a, fx)
        fails = []
        for st in s['stages']:
            if st['state'] not in ('PASS', 'NOT_APPLICABLE'):
                fails.append({'stage': st['stage'], 'code': st['code'],
                              'category': CODE_CAT.get(st['code'],
                                                       'OTHER_NAMED'),
                              'detail': st['detail'][:200]})
        results.append({'game_id': gid, 'status': s['status'],
                        'n_players': len(players), 'failures': fails,
                        # Additive: the full per-stage outcome, so a consumer
                        # need not infer PASS from absence-of-failure. Absence
                        # read as success is the defect this project pays for
                        # most often, and inferring it here would be that.
                        'stages': [{'stage': st['stage'],
                                    'state': st['state'], 'code': st['code']}
                                   for st in s['stages']],
                        'publication': s['publication']['code'],
                        'run_id': s['run_id']})
    return {'season': season, 'week': week, 'n_games': len(games),
            'model_configuration': model_configuration or 'PRODUCTION_BASELINE',
            'fixture_sources': {
                'state': fixture_sources.state.name,
                'code': fixture_sources.code,
                'sources': sorted(fixture_sources.value or {}),
                'detail_by_source': (fixture_sources.evidence or {}).get(
                    'detail_by_source'),
                'refusals': (fixture_sources.evidence or {}).get('refusals'),
            },
            'roster_source': src_file, 'n_roster_rows': len(rrows),
            'results': results}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--season', type=int, default=2026)
    ap.add_argument('--week', type=int, default=1)
    ap.add_argument('--out-dir', default='/tmp/v1r1')
    ap.add_argument('--written-at', default='2026-09-08T23:00:00Z')
    ap.add_argument('--model-configuration',
                    dest='model_configuration', default=None)
    a = ap.parse_args()
    r = build(a.season, a.week, a.out_dir, a.written_at,
              a.model_configuration)
    if 'fatal' in r:
        print('FATAL', r['fatal']); sys.exit(1)
    print(f"slate {r['season']} wk{r['week']}: {r['n_games']} games, roster "
          f"{r['roster_source']} ({r['n_roster_rows']} rows)")
    cat = collections.Counter(); st = collections.Counter()
    for g in r['results']:
        st[g['status']] += 1
        for f in g['failures']:
            cat[(f['category'], f['code'], f['stage'])] += 1
    print('\nSTATUS:', dict(st))
    print('\nFAILURE INVENTORY (category / code / stage -> games):')
    for (c, code, stg), n in cat.most_common():
        print(f'  {c:24s} {code:32s} {stg:22s} {n}')
    # THE INVENTORY GOES WHERE THE RUN WENT, AND THE PATH IS PRINTED.
    #
    # This wrote to the MODULE directory and ignored --out-dir, and printed
    # "wrote slate_inventory.json" with no path. Two consequences, both hit
    # on 2026-09-19: a baseline slate and a candidate slate with different
    # --out-dir silently overwrote each other's result, and a reader looking
    # in --out-dir found nothing and had to go searching for a file the
    # program said it had written.
    #
    # "Do not infer artifact existence from printed output" cuts both ways.
    # A program that reports a bare filename is asking to be inferred from.
    out = os.path.join(a.out_dir, 'slate_inventory.json')
    os.makedirs(a.out_dir, exist_ok=True)
    with open(out, 'w') as fh:
        json.dump(r, fh, indent=1)
    print(f'\nwrote {os.path.abspath(out)} '
          f'({os.path.getsize(out)} bytes, {len(r["results"])} game(s), '
          f'configuration {r["model_configuration"]})')
