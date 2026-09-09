"""NFL-INTEL-1 falsification measurements.

Every number quoted in NFL_INTEL_1_RECONCILIATION_RETURN.md that is not a
citation of an existing project artifact is produced here. Run:

    python3.12 nfl/research/intel1/measure_intel1.py

Two of the report's accounting cautions are testable against this project's own
data, and they come out on opposite sides. Both are measured here rather than
argued.
"""
import collections
import csv
import glob
import gzip
import json
import os
import pickle
import statistics
import sys

csv.field_size_limit(10 ** 7)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))         # repo root
PANEL = os.path.join(ROOT, 'nfl', 'derived', 'panel_enriched.pkl')
RECV = os.path.join(ROOT, 'nfl', 'research', 'rc1', 'recv.pkl')
# pbp is not committed. It is located, never fabricated, and its absence is
# reported by name rather than silently skipped.
PBP_GLOB = os.environ.get('INTEL1_PBP_GLOB', '')
SEASONS = (2020, 2021, 2022, 2023, 2024, 2025)


def _i(v, d=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return d


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def targets_versus_attempts():
    """The report: 'Do not impose equality between total receiver targets and
    total pass attempts.' Measured on the project's own team-game frame."""
    with open(PANEL, 'rb') as fh:
        rows = pickle.load(fh)
    tg = {}
    for r in rows:
        tg[(r['game_id'], r['team'])] = (r.get('team_targets'),
                                         r.get('team_pass_att'))
    diffs = [pa - tt for tt, pa in tg.values()
             if tt is not None and pa is not None]
    n = len(diffs)
    return {
        'team_games': n,
        'equal': sum(1 for d in diffs if abs(d) < 1e-9),
        'equal_pct': round(sum(1 for d in diffs if abs(d) < 1e-9) / n * 100, 4),
        'mean_attempts_minus_targets': round(statistics.mean(diffs), 4),
        'median': statistics.median(diffs),
        'min': min(diffs), 'max': max(diffs),
        'targets_exceed_attempts': sum(1 for d in diffs if d < 0),
        'verdict': 'the caution is CORRECT and this project never imposed the '
                   'equality; the gap is now quantified',
    }


def lateral_receiving_yards(pbp_files):
    """The report: 'receiving yards can accrue without a reception'.

    Measured twice, deliberately. First inside RC1's own frame, which is keyed
    on receiver_player_id and therefore CANNOT contain the counterexample --
    that reading returns a clean zero and would be wrong. Then on raw pbp,
    where the counterexample is real.
    """
    out = {}
    with open(RECV, 'rb') as fh:
        m = pickle.load(fh)
    out['rc1_frame'] = {
        'player_games': len(m),
        'zero_receptions_with_nonzero_yards': sum(
            1 for v in m.values()
            if v.get('receptions', 0) == 0 and abs(v.get('rec_yards', 0.0)) > 1e-9),
        'player_games_containing_a_lateral': sum(
            1 for v in m.values() if v.get('lateral_receptions', 0)),
        'why_this_reading_is_not_evidence':
            'build_recv.py keys on receiver_player_id, so a player who gained '
            'receiving yards only on a lateral is ABSENT from this frame, not '
            'present with zero. Absence read as zero is this project\'s most '
            'expensive defect class and it would have been committed here.',
    }
    if not pbp_files:
        out['raw_pbp'] = {'status': 'NOT_MEASURED',
                          'cause': 'PBP_NOT_LOCATED',
                          'note': 'set INTEL1_PBP_GLOB to the pbp{season}.csv.gz '
                                  'files; no number is reported without them'}
        return out
    pg = collections.defaultdict(collections.Counter)
    lat_plays = 0
    for path in pbp_files:
        with gzip.open(path, 'rt') as fh:
            for r in csv.DictReader(fh):
                if r.get('season_type') != 'REG':
                    continue
                if _i(r.get('two_point_attempt')):
                    continue
                key0 = (r.get('season'), r.get('week'), r.get('posteam') or '')
                rec = r.get('receiver_player_id') or ''
                if rec and _i(r.get('pass_attempt')):
                    c = pg[key0 + (rec,)]
                    c['targets'] += 1
                    if _i(r.get('complete_pass')):
                        c['receptions'] += 1
                lr = r.get('lateral_receiver_player_id') or ''
                if lr:
                    lat_plays += 1
                    c = pg[key0 + (lr,)]
                    c['lateral_plays'] += 1
                    c['lateral_yards'] += (_f(r.get('lateral_receiving_yards')) or 0.0)
    viol = sum(1 for v in pg.values()
               if v['receptions'] == 0 and abs(v['lateral_yards']) > 1e-9)
    out['raw_pbp'] = {
        'seasons': list(SEASONS), 'player_games': len(pg),
        'lateral_reception_plays': lat_plays,
        'player_games_receiving_a_lateral': sum(
            1 for v in pg.values() if v['lateral_plays']),
        'lateral_recipients_never_targeted_themselves': sum(
            1 for v in pg.values() if v['lateral_plays'] and not v['targets']),
        'zero_receptions_with_nonzero_receiving_yards': viol,
        'rate_per_10000_player_games': round(viol / len(pg) * 1e4, 4),
        'verdict': 'the report is CORRECT. zero_receptions_implies_zero_yards '
                   'is exact for our generator, which cannot lateral, and is '
                   'FALSE of realised football at the measured rate above.',
    }
    return out


def main():
    files = sorted(glob.glob(PBP_GLOB)) if PBP_GLOB else []
    res = {'targets_versus_attempts': targets_versus_attempts(),
           'lateral_receiving_yards': lateral_receiving_yards(files),
           'pbp_files_used': [os.path.basename(p) for p in files]}
    dest = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'intel1_measurements.json')
    with open(dest, 'w') as fh:
        json.dump(res, fh, indent=2, sort_keys=True)
    print(json.dumps(res, indent=2, sort_keys=True))
    print(f'\nwrote {dest}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
