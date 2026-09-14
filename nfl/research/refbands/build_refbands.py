"""Build every reference-band artifact. Diagnostic only.

    python3.12 nfl/research/refbands/build_refbands.py

Writes, all under paths resolved by `nfl/tools/nflwrite.resolve` so a wrong
working directory cannot place them outside the repository:

    nfl/research/refbands/USAGE_PANEL.csv.gz        the consumed frame itself
    nfl/research/refbands/REFERENCE_BANDS.jsonl.gz every band, every level
    nfl/research/refbands/REFERENCE_BANDS.json      headline bands + metadata
    nfl/research/refbands/RECENT_2025_SUPPLEMENT.json
    nfl/research/refbands/TONIGHT_DEN_KC_PLACEMENT.json

The panel is committed for the same reason the sibling MLB project's corpus
should have been: a band whose input is not on disk is a number nobody can
re-derive.
"""
from __future__ import annotations

import collections
import csv
import gzip
import hashlib
import io
import json
import pathlib
import sys

import numpy as np

_ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from nfl.research.refbands import refbands as R          # noqa: E402
from nfl.tools.nflwrite import resolve                   # noqa: E402

OUT = 'nfl/research/refbands'

# The four players the DEN@KC board is being read against, and the sealed
# conditional-on-participation projections handed to this workstream.
SEALED_RUN = ('nfl/research/live/2026_01_DEN_KC/'
              'PRELIMINARY_PROVISIONAL_V1_CANDIDATE_R8/f91342d6787a66a1')
TONIGHT = [
    {'who': 'Patrick Mahomes', 'player_id': '00-0033873', 'team': 'KC',
     'roles': ['QB1'], 'metric': 'attempts', 'projection': 34.36,
     'board_metric': 'qb/att'},
    {'who': 'Patrick Mahomes', 'player_id': '00-0033873', 'team': 'KC',
     'roles': ['QB1'], 'metric': 'pass_yards', 'projection': 244.92,
     'board_metric': 'qb/pyds'},
    {'who': 'Bo Nix', 'player_id': '00-0039732', 'team': 'DEN',
     'roles': ['QB1'], 'metric': 'attempts', 'projection': 32.08,
     'board_metric': 'qb/att'},
    {'who': 'Bo Nix', 'player_id': '00-0039732', 'team': 'DEN',
     'roles': ['QB1'], 'metric': 'pass_yards', 'projection': 212.56,
     'board_metric': 'qb/pyds'},
    {'who': 'Kenneth Walker III (KC RB1)', 'player_id': '00-0038134',
     'team': 'KC', 'roles': ['RB1', 'RUSH1'], 'metric': 'carries',
     'projection': 12.85, 'board_metric': 'rushing/carries'},
    {'who': 'Emmett Johnson (KC RB2)', 'player_id': '00-0041013',
     'team': 'KC', 'roles': ['RB2', 'RUSH2'], 'metric': 'carries',
     'projection': 6.36, 'board_metric': 'rushing/carries'},
]


def write(relpath: str, data: bytes) -> dict:
    if not data:
        raise R.EmptyStageError(
            f'REFBANDS_EMPTY_ARTIFACT: refusing to write 0 bytes to {relpath}.')
    t = resolve(f'{OUT}/{relpath}' if '/' not in relpath else relpath)
    t.parent.mkdir(parents=True, exist_ok=True)
    t.write_bytes(data)
    d = hashlib.sha256(data).hexdigest()
    print(f'  wrote {t.relative_to(_ROOT)}  {len(data)} bytes  sha256 {d[:16]}')
    return {'path': str(t.relative_to(_ROOT)), 'bytes': len(data),
            'sha256': d}


def panel_csv(rows) -> bytes:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(R.PANEL_FIELDS) + ['roles',
                                                               'starter_class'])
    w.writeheader()
    for r in rows:
        w.writerow({k: (';'.join(r['roles']) if k == 'roles' else r.get(k, ''))
                    for k in list(R.PANEL_FIELDS) + ['roles',
                                                     'starter_class']})
    raw = buf.getvalue().encode()
    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode='wb', compresslevel=9, mtime=0) as gz:
        gz.write(raw)
    return out.getvalue()


def load_2025_supplement():
    """2025 REG usage from the committed `panel_p3` leaf.

    2025 IS LAWFUL: every one of its games finished in January 2026, eight
    months before this board's cutoff. It is NOT in the coordinator's stated
    2021-2024 frame and it is NOT in this repository's play-by-play corpus --
    there is no `pbp_2025` blob -- so it is reported SEPARATELY and on the
    reduced metric set `panel_p3` carries. In particular `panel_p3` stores
    `pass_att_as_passer`, which is nflverse `pass_attempt` and therefore
    att_raw; official attempts are NOT derivable from this leaf because it
    does not store sacks. Nothing here is merged into a band built from
    play-by-play."""
    rows = []
    with gzip.open(R.PANEL_P3, 'rt') as fh:
        for r in csv.DictReader(fh):
            s = int(r['season'])
            if s not in R.PANEL_SEASONS:
                continue
            R.assert_lawful_season(s)
            rows.append({
                'season': s, 'week': int(r['week']), 'team': r['team'],
                'game_id': r['game_id'], 'player_id': r['gsis_id'],
                'position': r['position'], 'name': r['player_name'],
                'att_raw': int(r['pass_att_as_passer'] or 0),
                'dropbacks': int(r['dropbacks_as_passer'] or 0),
                'carries': int(r['carries'] or 0),
                'targets': int(r['targets'] or 0),
                'route_proxy': int(r['pass_snaps'] or 0),
                'offense_pct': r['offense_pct'],
            })
    if not rows:
        raise R.EmptyStageError('REFBANDS_2025_SUPPLEMENT_EMPTY')
    return rows


def reconcile(pbp_rows, p3_rows) -> dict:
    """pbp-derived vs panel_p3-derived, on the seasons they share.

    Two independent derivations of the same quantity that disagree are a
    finding. Two that are never compared are a liability."""
    key = lambda r: (r['game_id'], r['player_id'])
    p3 = {key(r): r for r in p3_rows if r['season'] in R.PBP_SEASONS}
    stats = collections.Counter()
    diffs = collections.defaultdict(list)
    for r in pbp_rows:
        o = p3.get(key(r))
        if o is None:
            stats['pbp_row_absent_from_panel_p3'] += 1
            continue
        stats['matched'] += 1
        for m in ('att_raw', 'carries', 'targets'):
            diffs[m].append(r[m] - o[m])
    out = {'matched_rows': stats['matched'],
           'pbp_rows_absent_from_panel_p3':
               stats['pbp_row_absent_from_panel_p3']}
    for m, d in diffs.items():
        a = np.asarray(d, float)
        out[m] = {'mean_pbp_minus_p3': round(float(a.mean()), 5),
                  'n_nonzero': int((a != 0).sum()),
                  'max_abs': int(np.abs(a).max()) if a.size else 0}
    return out


def _subsets(spec, role, panel_rows):
    """The exact row subset behind each rung, built from the panel rather than
    by parsing a key back into a filter. Parsing the key was the first version
    and it silently returned the player's whole history for the recent-window
    rung, because `last8` is not a filter expressible over a single row."""
    pid, team = spec['player_id'], spec['team']
    mine = [r for r in panel_rows
            if role in r['roles'] and r['player_id'] == pid]
    recent = sorted(mine, key=lambda x: (x['season'], x['week'])
                    )[-R.RECENT_WINDOW:]
    return {
        'player_role_recent': recent,
        'player_role_season': [r for r in mine if r['season'] == 2024],
        'player_role': mine,
        'role_team': [r for r in panel_rows
                      if role in r['roles'] and r['team'] == team],
        'role': [r for r in panel_rows if role in r['roles']],
    }


def ladder_for(recs_by_key, spec, panel_rows):
    """The band ladder for one player-metric, finest level first."""
    pid, m = spec['player_id'], spec['metric']
    out = []
    for role in spec['roles']:
        subs = _subsets(spec, role, panel_rows)
        rungs = (
            ('player_role_recent',
             f'player:{pid}|role:{role}|last{R.RECENT_WINDOW}'),
            ('player_role_season', f'player:{pid}|role:{role}|season:2024'),
            ('player_role', f'player:{pid}|role:{role}'),
            ('role_team', f'role:{role}|team:{spec["team"]}'),
            ('role', f'role:{role}'),
        )
        for lvl, k in rungs:
            rec = recs_by_key.get((k, m))
            if rec is None:
                out.append({'level': lvl, 'key': k, 'metric': m, 'n': 0,
                            'role': role, 'status': R.INSUFFICIENT,
                            'reason': 'the player holds this role in no '
                                      'lawful game in the frame',
                            'band': None})
                continue
            e = {kk: rec[kk] for kk in ('level', 'key', 'metric', 'n',
                                        'n_clusters', 'status', 'adequacy',
                                        'own', 'band', 'band_source',
                                        'parent_key')}
            e['role'] = role
            e['reason'] = rec.get('reason')
            vals, clus = R._vals(subs[lvl], m)
            if len(vals) != rec['n']:
                raise R.EmptyStageError(
                    f'REFBANDS_LADDER_SUBSET_MISMATCH: {k}/{m} rebuilt '
                    f'{len(vals)} rows against the recorded n={rec["n"]}. '
                    f'The ladder and the hierarchy disagree about what the '
                    f'group is, which makes every number on this rung '
                    f'unreadable.')
            if vals:
                e['projection_percentile_in_own_sample'] = round(
                    R.percentile_of(spec['projection'], vals), 1)
                e['inside_own_p10_p90'] = bool(
                    rec['own']['p10'] <= spec['projection']
                    <= rec['own']['p90'])
                e['projection_percentile_in_shrunk_band'] = _place_in_band(
                    spec['projection'], rec['band'])
                if rec['n'] >= R.N_FLOOR:
                    e['clustered_ci_p50'] = R.clustered_band_ci(vals, clus, 50)
            out.append(e)
    return out


def _place_in_band(x, band):
    """Where a value falls against a SHRUNK band, which has no sample behind
    it. Reported as the bracketing pair, never as a fake percentile."""
    if band is None:
        return None
    pts = [(L, band[f'p{L}']) for L in R.LEVELS]
    if x < pts[0][1]:
        return 'below p10'
    if x > pts[-1][1]:
        return 'above p90'
    for (a, va), (b, vb) in zip(pts, pts[1:]):
        if va <= x <= vb:
            return f'p{a}-p{b}'
    return None


def main() -> int:
    print('refbands: building the play-by-play usage panel '
          f'({R.PBP_SEASONS})')
    rows = R.assign_roles(R.build_pbp_panel())
    tg = {(r['game_id'], r['team']) for r in rows}
    print(f'  {len(rows)} player-team-game rows, {len(tg)} team-games, '
          f'{len({r["game_id"] for r in rows})} games')
    if len(tg) != 2174:
        print(f'  NOTE: {len(tg)} team-games, not the 2174 the broad bands '
              f'were measured on. Investigate before quoting.')

    manifest = {'usage_panel': write('USAGE_PANEL.csv.gz', panel_csv(rows))}

    print('refbands: building the hierarchy')
    recs = R.build_hierarchy(rows)
    print(f'  {len(recs)} band records')
    by_level = collections.Counter(r['level'] for r in recs)
    by_status = collections.Counter(r['status'] for r in recs)
    payload = ''.join(json.dumps(r, sort_keys=True) + '\n' for r in recs)
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode='wb', compresslevel=9, mtime=0) as gz:
        gz.write(payload.encode())
    manifest['all_bands'] = write('REFERENCE_BANDS.jsonl.gz', buf.getvalue())
    manifest['all_bands']['bytes_uncompressed'] = len(payload)
    insufficient = collections.Counter()
    total_by_level = collections.Counter()
    for r in recs:
        total_by_level[r['level']] += 1
        if r['status'] == R.INSUFFICIENT:
            insufficient[r['level']] += 1
    insufficient_summary = {
        lvl: {'records': total_by_level[lvl],
              'insufficient_evidence': insufficient[lvl],
              'share': round(insufficient[lvl] / total_by_level[lvl], 4)}
        for lvl in sorted(total_by_level)}

    recs_by_key = {(r['key'], r['metric']): r for r in recs}

    print('refbands: clustered intervals on the headline bands')
    headline = []
    for r in recs:
        if r['level'] not in ('position', 'role') or r['own'] is None:
            continue
        role = r['key'].split(':')[1]
        sub = ([x for x in rows if role in x['roles']] if r['level'] == 'role'
               else [x for x in rows
                     if (x['position'] == role
                         or (role == 'ANYRUSHER' and x['carries'] > 0))])
        vals, clus = R._vals(sub, r['metric'])
        e = dict(r)
        e['clustered_ci'] = {str(L): R.clustered_band_ci(vals, clus, L)
                             for L in (10, 50, 90)}
        headline.append(e)
    print(f'  {len(headline)} headline bands')

    print('refbands: 2025 supplement and cross-source reconciliation')
    p3 = load_2025_supplement()
    rec25 = reconcile(rows, p3)
    print(f'  reconciliation: {rec25["matched_rows"]} rows matched')

    sup = {}
    p3_2025 = [r for r in p3 if r['season'] == 2025]
    by_tg = collections.defaultdict(list)
    for r in p3_2025:
        by_tg[(r['game_id'], r['team'])].append(r)
    lead = collections.defaultdict(list)
    for tgk, g in by_tg.items():
        qb = sorted([x for x in g if x['dropbacks'] > 0],
                    key=lambda x: (-x['dropbacks'], x['player_id']))
        for i, x in enumerate(qb[:2], 1):
            lead[f'QB{i}'].append(x)
        ru = sorted([x for x in g if x['carries'] > 0],
                    key=lambda x: (-x['carries'], x['player_id']))
        for i, x in enumerate(ru[:2], 1):
            lead[f'RUSH{i}'].append(x)
    for role, g in lead.items():
        for m in (('att_raw',) if role.startswith('QB') else ('carries',)):
            sup[f'2025|role:{role}|{m}'] = R.raw_band([x[m] for x in g])
    # MEASURED, and it is a trap for anyone else reading this leaf:
    # panel_p3 `dropbacks_as_passer` equals `pass_att_as_passer` in EVERY one
    # of its rows. It is not a dropback count under a second name; scrambles
    # are charged to the rusher, so no scramble ever reaches the passer's
    # column, and sacks are already inside pass_attempt. The leaf carries no
    # true dropback column and a band built on it would be att_raw twice.
    dup_eq = sum(1 for r in p3 if r['att_raw'] == r['dropbacks'])
    dup_all = len(p3)
    sup_players = {}
    for spec in TONIGHT:
        pid = spec['player_id']
        mine = [r for r in p3 if r['player_id'] == pid]
        for season in (2024, 2025):
            s = [r for r in mine if r['season'] == season]
            m = ('att_raw' if spec['metric'] in ('attempts', 'att_raw')
                 else 'carries' if spec['metric'] == 'carries' else None)
            if m is None:
                continue
            k = f'{season}|player:{pid}|{m}'
            if k in sup_players:
                continue
            sup_players[k] = (R.raw_band([r[m] for r in s]) if s else
                              {'n': 0, 'status': R.INSUFFICIENT})
    manifest['supplement'] = write('RECENT_2025_SUPPLEMENT.json', json.dumps({
        'artifact': 'REFBANDS_2025_SUPPLEMENT',
        'spec_version': R.SPEC_VERSION,
        'source': 'nfl/research/inputs/panel_p3.csv.gz',
        'lawful_because': ('every 2025 REG game finished in January 2026, '
                           'before the 2026-09-14T17:40:19Z cutoff'),
        'not_in_pbp_corpus': ('there is no pbp_2025 blob under '
                              'nfl/research/postgame/, so passing YARDS, '
                              'official ATTEMPTS, receptions and receiving '
                              'yards are not derivable for 2025 in this '
                              'repository. This is the single highest-value '
                              'missing lawful input for this workstream.'),
        'metric_caveat': ('att_raw here is nflverse pass_attempt and INCLUDES '
                          'sacks and spikes. It is NOT the board qb/att.'),
        'cross_source_reconciliation_2021_2024': rec25,
        'panel_p3_dropback_column_is_att_raw': {
            'rows_checked': dup_all, 'rows_equal': dup_eq,
            'finding': ('dropbacks_as_passer == pass_att_as_passer in every '
                        'row. panel_p3 carries no true dropback column.')},
        'player_games_present': {
            pid: sorted(r['week'] for r in p3
                        if r['player_id'] == pid and r['season'] == 2025)
            for pid in sorted({s2['player_id'] for s2 in TONIGHT})},
        'role_bands_2025': sup,
        'tonight_players': sup_players,
    }, indent=1, sort_keys=True).encode())

    print('refbands: definition sensitivity on the QB attempt metric')
    qb1 = [r for r in rows if 'QB1' in r['roles']]
    sens = {'why': ('the broad bands this work extends label their QB1 band '
                    '"pass attempts". It reproduces EXACTLY and ONLY against '
                    'att_raw, which includes sacks and spikes. The board '
                    'metric qb/att is the other quantity. The two bands are '
                    'given here side by side so the gap is a number, not an '
                    'opinion.'),
            'per_team_game_mean_gap_att_raw_minus_attempts':
                round(float(np.mean([r['att_raw'] - r['attempts']
                                     for r in qb1])), 4),
            'bands': {m: R.raw_band([r[m] for r in qb1])
                      for m in ('attempts', 'att_raw', 'dropbacks')},
            'tonight_percentile_under_each_definition': {
                spec['who']: {m: round(R.percentile_of(
                    spec['projection'], [r[m] for r in qb1]), 1)
                    for m in ('attempts', 'att_raw', 'dropbacks')}
                for spec in TONIGHT if spec['metric'] == 'attempts'}}
    print('  ' + json.dumps(sens['tonight_percentile_under_each_definition']))

    print('refbands: tonight')
    tonight = []
    for spec in TONIGHT:
        led = ladder_for(recs_by_key, spec, rows)
        finest = next((e for e in led
                       if e.get('status') in ('OWN', 'OWN_DOMINANT', 'SHRUNK')
                       and e.get('n', 0) >= R.N_FLOOR), None)
        tonight.append({**spec, 'ladder': led,
                        'finest_with_support': finest['key'] if finest
                                               else None})
    manifest['tonight'] = write('TONIGHT_DEN_KC_PLACEMENT.json', json.dumps({
        'artifact': 'REFBANDS_TONIGHT_PLACEMENT',
        'spec_version': R.SPEC_VERSION,
        'sealed_run': SEALED_RUN,
        'forecast_cutoff': R.FORECAST_CUTOFF,
        'contract': ('A placement is a DIAGNOSTIC READING. It is never a '
                     'reason to move a projection. A projection outside a '
                     'band may be the model working.'),
        'placements': tonight,
    }, indent=1, sort_keys=True).encode())

    manifest['headline'] = write('REFERENCE_BANDS.json', json.dumps({
        'artifact': 'NFL_REFERENCE_BANDS',
        'spec_version': R.SPEC_VERSION,
        'purpose': ('DIAGNOSTIC ONLY. A band answers whether a conditional '
                    'projection is unusually low or high against history. It '
                    'is never a floor, a cap, a correction or a model input.'),
        'forecast_cutoff': R.FORECAST_CUTOFF,
        'frame': {'seasons': list(R.PBP_SEASONS), 'season_type': 'REG',
                  'team_games': len(tg), 'games': len({r['game_id']
                                                       for r in rows}),
                  'player_team_game_rows': len(rows),
                  'grouping': 'GROUP BY (game_id, posteam), never game_id'},
        'definitions': {
            'attempts': 'pass_attempt & !sack & !qb_spike -- the board qb/att '
                        'and nfl/research/qb2/build_qb.py `attempts`',
            'att_raw': 'nflverse pass_attempt, INCLUDES sacks and spikes',
            'dropbacks': 'att_raw + scrambles - spikes',
            'carries': 'rush_attempt & !qb_kneel',
            'targets': 'pass_attempt with a receiver_player_id',
            'route_proxy': 'ROUTE_PROXY_PASS_PARTICIPATION -- panel_p3 '
                           'pass_snaps, presence on the field for a team '
                           'dropback. An UPPER BOUND on routes run, not a '
                           'route count.',
            'roles': 'observed within-team-game usage ranks, not depth chart',
            'quantile_method': 'numpy.percentile method="linear"',
        },
        'adequacy_rule': {
            'alpha': R.ALPHA,
            'n_min': {f'p{L}': R.n_min_for(L) for L in R.LEVELS},
            'derivation': 'n >= ln(alpha)/ln(1-t), t = min(p,1-p): the sample '
                          'size at which the sample is 95% likely to contain '
                          'an observation in the tail being reported',
            'n_floor': R.N_FLOOR,
        },
        'shrinkage_rule': {
            'form': 'w = n/(n+n0); band = w*own + (1-w)*parent',
            'n0': R.N0,
            'derivation': 'n0 = n_min_for(10) = 29, the sample size at which '
                          'the widest published quantile pair first becomes '
                          'estimable. NOT fitted; no outcome was consulted.',
            'monotone': 'a convex blend of two monotone bands is monotone',
        },
        'counts': {'records': len(recs), 'by_level': dict(by_level),
                   'by_status': dict(by_status)},
        'insufficient_evidence_by_level': insufficient_summary,
        'definition_sensitivity': sens,
        'headline_bands': headline,
        'artifacts': manifest,
    }, indent=1, sort_keys=True).encode())
    print('refbands: done')
    return 0


if __name__ == '__main__':
    sys.exit(main())
