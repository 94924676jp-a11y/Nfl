#!/usr/bin/env python3.12
"""ATL@NO postgame item 6 -- role / depth-chart / opportunity audit.

    python3.12 nfl/postgame/showdown_atl_no_role_audit.py [--ingest SNAP_2024 SNAP_2025 PLAYERS_CSV SNAP_2026]

LAYER: POSTGAME_DIAGNOSIS. Reads the sealed v2 projection (RW_INACTIVES_CHARTFIX), the truth package, 2026 snap
counts and (for the historical test) 2024-25 nflverse snap counts + pbp. Writes ATL_NO_ROLE_AUDIT.json. Changes no
projection.

Every defect here is DEFINED FROM PREGAME INFORMATION (the projection against evidence that existed before kickoff);
the realised game is reported beside it as grading, never used to define it.

A  OPPORTUNITY TABLE   projected unconditional (sim worlds), if-plays (conditional_volume), P(plays), actual, snaps.
B  APPEARANCE TEST     The allocator's P(plays) for a field is the population appearance rate AT THE DEPTH RANK
                       (proj_v1 ~L879). It does not condition on the player's own recent participation, nor on being
                       officially active. Historical test (2024-25, out of the 2026 season entirely): among RB/WR/TE
                       who were DRESSED (any snap) and recorded >=1 opportunity in that field in each of their team's
                       previous 3 games, how often did they record zero? That rate is set beside 1 - P(plays) the model
                       gave the ATL@NO players who met the same pregame condition (2026 weeks 1-3).
C  VACATED VOLUME      where the inactive Etienne / Fant volume was projected to go vs the pregame snap shares.
D  LABELLING           SHOWDOWN_*_PROJECTIONS.csv volume columns are IF-PLAYS values printed beside an UNCONDITIONAL
                       sim_mean, with no label saying so.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import hashlib
import json
import pathlib
import shutil
import sys

import numpy as np
import pandas as pd

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import kicker_world as KW  # noqa: E402
from nfl.market import atl_no_prop_shadow as PS  # noqa: E402

GAME = '2026_04_ATL_NO'
SD = _REPO / 'nfl/dfs/salaries/showdown_atl_no/RW_INACTIVES_CHARTFIX'
OUT = _REPO / 'nfl/postgame/showdown_atl_no_2026W4'
RAW = _REPO / 'nfl/postgame/raw/showdown_atl_no_2026W4'
HIST_RAW = _REPO / 'nfl/postgame/raw/role_audit_history'
URLS = {'snap_counts_2024': 'https://github.com/nflverse/nflverse-data/releases/download/snap_counts/snap_counts_2024.csv',
        'snap_counts_2025': 'https://github.com/nflverse/nflverse-data/releases/download/snap_counts/snap_counts_2025.csv',
        'snap_counts_2026': 'https://github.com/nflverse/nflverse-data/releases/download/snap_counts/snap_counts_2026.csv',
        'players': 'https://github.com/nflverse/nflverse-data/releases/download/players/players.csv'}
FIELDS = {'carries': 'RB', 'targets': ('RB', 'WR', 'TE')}
N_BOOT = 1000
BOOT_SEED = 20261006


class RoleAuditError(RuntimeError):
    pass


def _sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def ingest(snap24, snap25, players, snap26=None):
    """Preserve the historical inputs immutably (content-addressed). players.csv is reduced to the id crosswalk; the
    full file's hash is recorded so the reduction is verifiable."""
    HIST_RAW.mkdir(parents=True, exist_ok=True)
    prov = []
    for kind, src in (('snap_counts_2024', snap24), ('snap_counts_2025', snap25)):
        b = pathlib.Path(src).read_bytes()
        h = _sha_bytes(b)
        dst = HIST_RAW / f'{kind}.{h[:16]}.csv.gz'
        if not dst.exists():
            dst.write_bytes(gzip.compress(b, mtime=0))
        prov.append({'kind': kind, 'url': URLS[kind], 'sha256_uncompressed': h, 'file': str(dst.relative_to(_REPO))})
    b = pathlib.Path(players).read_bytes()
    full = _sha_bytes(b)
    p = pd.read_csv(players, usecols=['gsis_id', 'pfr_id', 'position', 'display_name'], low_memory=False)
    p = p.dropna(subset=['gsis_id', 'pfr_id'])
    red = p.to_csv(index=False).encode()
    dst = HIST_RAW / f'players_crosswalk.{_sha_bytes(red)[:16]}.csv.gz'
    if not dst.exists():
        dst.write_bytes(gzip.compress(red, mtime=0))
    prov.append({'kind': 'players_crosswalk', 'url': URLS['players'], 'full_file_sha256': full,
                 'reduced_columns': ['gsis_id', 'pfr_id', 'position', 'display_name'],
                 'sha256_reduced': _sha_bytes(red), 'file': str(dst.relative_to(_REPO))})
    stamp = dt.datetime.now(dt.timezone.utc).isoformat()
    if snap26:
        b = pathlib.Path(snap26).read_bytes()
        h = _sha_bytes(b)
        dst = RAW / f'SNAP_COUNTS_2026.{h[:16]}.csv.gz'
        if not dst.exists():
            dst.write_bytes(gzip.compress(b, mtime=0))
        (RAW / 'SNAP_COUNTS_2026.PROVENANCE.json').write_text(json.dumps(
            {'kind': 'SNAP_COUNTS_2026_POSTGAME', 'url': URLS['snap_counts_2026'], 'retrieved_at': stamp,
             'sha256_uncompressed': h, 'file': str(dst.relative_to(_REPO)), 'IMMUTABLE': True,
             'USE': 'postgame grading only (actual snap shares); weeks 1-3 rows are the pregame evidence the projection had'},
            indent=1))
    (HIST_RAW / 'PROVENANCE.json').write_text(json.dumps({'ARTIFACT': 'ROLE_AUDIT_HISTORY_RAW', 'retrieved_at': stamp,
                                                         'files': prov, 'IMMUTABLE': True}, indent=1))


def _one(d, pat):
    c = sorted(d.glob(pat))
    if len(c) != 1:
        raise RoleAuditError(f'AMBIGUOUS_OR_MISSING {d}/{pat}: {[x.name for x in c]}')
    return c[0]


def _opps(pbp_paths, seasons=None):
    cols = ['game_id', 'season', 'week', 'season_type', 'posteam', 'receiver_player_id', 'rusher_player_id',
            'play_type', 'qb_scramble']
    fr = []
    for p in pbp_paths:
        df = pd.read_csv(p, usecols=lambda c: c in cols, low_memory=False)
        df = df[df.season_type == 'REG']
        if seasons:
            df = df[df.season.isin(seasons)]
        fr.append(df)
    df = pd.concat(fr, ignore_index=True)
    t = df[df.receiver_player_id.notna()].groupby(['game_id', 'receiver_player_id']).size().rename('targets')
    run = df[(df.play_type == 'run') & df.rusher_player_id.notna() & (df.qb_scramble.fillna(0) == 0)]
    c = run.groupby(['game_id', 'rusher_player_id']).size().rename('carries')
    o = pd.concat([t.rename_axis(['game_id', 'gsis_id']), c.rename_axis(['game_id', 'gsis_id'])], axis=1).fillna(0)
    return o.reset_index()


def appearance_history():
    prov = json.loads((HIST_RAW / 'PROVENANCE.json').read_text())
    f = {x['kind']: _REPO / x['file'] for x in prov['files']}
    cw = pd.read_csv(f['players_crosswalk'])
    snaps = pd.concat([pd.read_csv(f['snap_counts_2024']), pd.read_csv(f['snap_counts_2025'])], ignore_index=True)
    snaps = snaps[(snaps.game_type == 'REG') & snaps.position.isin(['RB', 'WR', 'TE'])]
    snaps = snaps.merge(cw[['pfr_id', 'gsis_id']], left_on='pfr_player_id', right_on='pfr_id', how='inner')
    pbp = [p for s, p in KW._pbp_paths().items() if int(s) in (2024, 2025)]
    if len(pbp) != 2:
        raise RoleAuditError(f'PBP_2024_2025_MISSING {pbp}')
    o = _opps(pbp)
    x = snaps.merge(o, on=['game_id', 'gsis_id'], how='left').fillna({'targets': 0, 'carries': 0})
    x = x.sort_values(['gsis_id', 'season', 'week'])
    # team game index so "previous 3 games" means the team's previous 3 games, not the player's
    tg = x[['season', 'team', 'week']].drop_duplicates().sort_values(['season', 'team', 'week'])
    tg['tgi'] = tg.groupby(['season', 'team']).cumcount()
    x = x.merge(tg, on=['season', 'team', 'week'])
    out = {}
    for field, pos in FIELDS.items():
        pos = (pos,) if isinstance(pos, str) else pos
        y = x[x.position.isin(pos)].copy()
        y['has'] = (y[field] > 0).astype(int)
        key = y.set_index(['gsis_id', 'season', 'team', 'tgi'])['has'].to_dict()
        prior = [all(key.get((r.gsis_id, r.season, r.team, r.tgi - k)) == 1 for k in (1, 2, 3))
                 for r in y.itertuples()]
        y['prior3_all'] = prior
        z = y[y.prior3_all]
        zero = (z.has == 0).astype(float)
        rng = np.random.default_rng(BOOT_SEED)
        g = z.game_id.to_numpy()
        ug = np.unique(g)
        idx = {k: np.flatnonzero(g == k) for k in ug}
        bs = [zero.to_numpy()[np.concatenate([idx[k] for k in rng.choice(ug, len(ug))])].mean() for _ in range(N_BOOT)]
        by_pos = {p: {'n': int((z.position == p).sum()),
                      'p_zero': round(float(zero[z.position == p].mean()), 4) if (z.position == p).any() else None}
                  for p in pos}
        out[field] = {'positions': list(pos), 'n_player_games': int(len(z)), 'n_games': int(len(ug)),
                      'p_zero_given_dressed_and_prior3_all_ge1': round(float(zero.mean()), 4),
                      'ci95_game_clustered': [round(float(np.percentile(bs, 2.5)), 4), round(float(np.percentile(bs, 97.5)), 4)],
                      'by_position': by_pos}
    return out, prov


def slate():
    proj = json.loads(_one(SD, 'SHOWDOWN_*_2026W4_PROJ.json').read_text())['rows']
    csvr = {(r['player'], r['team']): r for r in csv.DictReader(open(_one(SD, 'SHOWDOWN_*_PROJECTIONS.csv')))}
    stats, _p, meta = PS.CR.load_worlds(_one(SD, 'SHOWDOWN_*_WORLDS.npz'))
    F = {f: i for i, f in enumerate(meta['fields'])}
    act = json.loads((OUT / 'ATL_NO_POSTGAME_ACTUAL.json').read_text())['player_actuals']
    return proj, csvr, stats, F, meta, act


def run():
    hist, prov = appearance_history()
    proj, csvr, stats, F, meta, act = slate()
    sc = pd.read_csv(_one(RAW, 'SNAP_COUNTS_2026.*.csv.gz'))
    sc = sc[(sc.season == 2026) & sc.team.isin(['ATL', 'NO'])]
    cw = pd.read_csv(_REPO / next(x['file'] for x in prov['files'] if x['kind'] == 'players_crosswalk'))
    sc = sc.merge(cw[['pfr_id', 'gsis_id']], left_on='pfr_player_id', right_on='pfr_id', how='left')
    p26 = _one(RAW, 'NFLVERSE_PBP_2026.*.csv.gz')
    o26 = _opps([p26], seasons=[2026])
    wk = pd.read_csv(p26, usecols=['game_id', 'week', 'posteam'], low_memory=False).drop_duplicates()
    o26 = o26.merge(wk.groupby('game_id').week.first().reset_index(), on='game_id')
    by_g = {r.get('gsis_id'): r for r in proj.values() if r.get('gsis_id')}
    prior_team_games = {t: sorted(sc[(sc.team == t) & (sc.week < 4)].game_id.unique()) for t in ('ATL', 'NO')}
    rows = []
    for i, k in enumerate(meta['keys']):
        name, team = k.split('|')
        pr = next((r for r in proj.values() if r.get('name') == name and (r.get('club') or r.get('team')) == team), {})
        pos = pr.get('position') or csvr.get((name, team), {}).get('pos')
        gid = pr.get('gsis_id')
        a = (act.get(k) or {}).get('stats', {})
        mine = (sc.gsis_id == gid) if gid else (sc.player == name)
        snap_row = sc[mine & (sc.team == team) & (sc.week == 4)]
        prior = sc[mine & (sc.team == team) & (sc.week < 4)].sort_values('week')
        rec = {'player': k, 'pos': pos, 'state': csvr.get((name, team), {}).get('state'),
               'depth_rank': csvr.get((name, team), {}).get('depth_rank'),
               'prior_snap_pct_wk1_3': [round(float(v), 2) for v in prior.offense_pct],
               'actual_snap_pct': None if snap_row.empty else round(float(snap_row.offense_pct.iloc[0]), 2)}
        for field in ('carries', 'targets'):
            w = stats[i, :, F[field]]
            pp = (pr.get('p_plays') or {}).get(field)
            cv = (pr.get('conditional_volume') or {}).get(field)
            prior_has = [int(((o26.gsis_id == gid) & (o26.game_id == g) & (o26[field] > 0)).any()) for g in prior_team_games[team]]
            rec[field] = {'sim_mean_unconditional': round(float(w.mean()), 2),
                          'sim_p_zero': round(float((w == 0).mean()), 3),
                          'p_plays': None if pp is None else round(float(pp), 3),
                          'if_plays_mean': None if cv is None else round(float(cv), 2),
                          'csv_column_value': csvr.get((name, team), {}).get(field),
                          'pregame_games_with_ge1_wk1_3': prior_has,
                          'actual': a.get(field if field == 'carries' else 'targets', 0)}
        rows.append(rec)
    # B: the appearance defect, pregame-defined
    flagged = []
    for r in rows:
        for field in ('carries', 'targets'):
            f = r[field]
            if r['pos'] not in ((FIELDS[field],) if isinstance(FIELDS[field], str) else FIELDS[field]):
                continue
            if f['pregame_games_with_ge1_wk1_3'] == [1, 1, 1] and f['p_plays'] is not None:
                h = hist[field]['p_zero_given_dressed_and_prior3_all_ge1']
                h = hist[field]['p_zero_given_dressed_and_prior3_all_ge1']
                hi = hist[field]['ci95_game_clustered'][1]
                cv = f['if_plays_mean']
                flagged.append({'player': r['player'], 'field': field,
                                'allocator_1_minus_p_plays': round(1 - f['p_plays'], 3),
                                'sim_p_zero': f['sim_p_zero'], 'historical_p_zero_same_condition': h,
                                'historical_ci95': hist[field]['ci95_game_clustered'],
                                'DEFECT_MEAN_SHRINK': (1 - f['p_plays']) > 2 * hi,
                                'DEFECT_ZERO_MASS': f['sim_p_zero'] > 2 * hi,
                                'sim_mean_unconditional': f['sim_mean_unconditional'], 'if_plays_mean': cv,
                                'mean_at_historical_rate': None if cv is None else round((1 - h) * cv, 2),
                                'graded_actual': f['actual'], 'actual_snap_pct': r['actual_snap_pct']})
    n_def = sum(x['DEFECT_MEAN_SHRINK'] or x['DEFECT_ZERO_MASS'] for x in flagged)
    # C: vacated volume (inactive players' week 1-3 per-game volume) vs projected redistribution
    vac = {}
    for name, team, field in (('Travis Etienne Jr.', 'NO', 'carries'), ('Travis Etienne Jr.', 'NO', 'targets'),
                              ('Noah Fant', 'NO', 'targets')):
        r = next((r for r in proj.values() if r.get('name') == name), None)
        gid = r.get('gsis_id') if r else None
        per_g = float(o26[(o26.gsis_id == gid) & (o26.week < 4)][field].sum() / 3) if gid else None
        vac[f'{name}|{field}'] = {'vacated_per_game_wk1_3': None if per_g is None else round(per_g, 2)}
    grp = {'carries': ['Alvin Kamara|NO', 'Kendre Miller|NO', 'CJ Donaldson|NO'],
           'targets_TE': ['Juwan Johnson|NO', 'Oscar Delp|NO', 'Treyton Welch|NO']}
    redistribution = {}
    for g, ks in grp.items():
        field = 'carries' if g == 'carries' else 'targets'
        tot_proj = sum(next(r for r in rows if r['player'] == k)[field]['sim_mean_unconditional'] for k in ks)
        prior_snaps = {k: float(np.mean(next(r for r in rows if r['player'] == k)['prior_snap_pct_wk1_3'] or [0])) for k in ks}
        ssum = sum(prior_snaps.values()) or 1
        actual_snaps = {k: next(r for r in rows if r['player'] == k)['actual_snap_pct'] for k in ks}
        redistribution[g] = [{'player': k,
                              'projected_share': round(next(r for r in rows if r['player'] == k)[field]['sim_mean_unconditional'] / tot_proj, 3) if tot_proj else None,
                              'pregame_snap_share_wk1_3': round(prior_snaps[k] / ssum, 3),
                              'graded_actual_snap_pct': actual_snaps[k],
                              'graded_actual': next(r for r in rows if r['player'] == k)[field]['actual']} for k in ks]
    # D: labelling
    label = [{'player': r['player'], 'field': f, 'csv': r[f]['csv_column_value'], 'if_plays': r[f]['if_plays_mean'],
              'unconditional_sim': r[f]['sim_mean_unconditional']}
             for r in rows for f in ('carries', 'targets')
             if r[f]['csv_column_value'] not in (None, '') and abs(float(r[f]['csv_column_value']) - r[f]['sim_mean_unconditional']) > 0.25]
    doc = {'ARTIFACT': 'ATL_NO_ROLE_AUDIT', 'LAYER': 'POSTGAME_DIAGNOSIS', 'game': GAME,
           'sources': {'projection_dir': str(SD.relative_to(_REPO)), 'history_raw': prov['files'],
                       'snap_counts_2026': str(_one(RAW, 'SNAP_COUNTS_2026.*.csv.gz').relative_to(_REPO))},
           'A_opportunity_table': rows,
           'B_appearance_history_2024_2025': hist,
           'B_appearance_flags': flagged,
           'B_VERDICT': (f'DEFECT-APPEARANCE CONFIRMED on {n_def} player-fields' if n_def else 'NOT CONFIRMED'),
           'B_RULE': ('pregame condition: dressed + >=1 opportunity in the field in each of the team\'s previous 3 games. '
                      'Two expressions, each flagged when it exceeds TWICE the upper 95% bound of the historical rate '
                      '(game-clustered bootstrap): MEAN_SHRINK -- the allocator\'s 1 - P(plays), which multiplies the '
                      'if-plays volume into the unconditional mean the simulator centres on; ZERO_MASS -- the share of '
                      'simulated worlds with zero opportunity. Rule fixed in code before the flags were read; the '
                      'first version used 1 - P(plays) as a zero probability, which the worlds showed is not how the '
                      'simulator consumes it, so it was split -- the threshold itself is unchanged.'),
           'B_MECHANISM': ('proj_v1 allocation: appear[i] = depth table appearance_rate at the player\'s depth rank -- a '
                           'population rate over rostered players at that rank (including the injured, the inactive and '
                           'the unused). It ignores the player\'s own participation and the official ACTIVE status, both '
                           'known pregame. Known programme item B8 (appearance / zero-production process).'),
           'C_vacated_volume': vac, 'C_redistribution': redistribution,
           'D_labelling_mismatches': label,
           'D_FINDING': ('SHOWDOWN_*_PROJECTIONS.csv carries/targets/rec/yards columns are conditional_volume (IF he plays) '
                         'printed beside an UNCONDITIONAL sim_mean with no label. Reporting defect only: the simulator and '
                         'optimizer consume the worlds, not these columns.'),
           'NOT_A_FORECAST_INPUT': True, 'written_at': dt.datetime.now(dt.timezone.utc).isoformat()}
    p = OUT / 'ATL_NO_ROLE_AUDIT.json'
    p.write_text(json.dumps(doc, indent=1, default=float))
    return p, doc


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--ingest', nargs=4, metavar=('SNAP_2024', 'SNAP_2025', 'PLAYERS_CSV', 'SNAP_2026'))
    a = ap.parse_args()
    if a.ingest:
        ingest(*a.ingest)
    p, doc = run()
    print(p)
    print(json.dumps(doc['B_appearance_history_2024_2025'], indent=1))
    for x in doc['B_appearance_flags']:
        print(x)
    print(doc['B_VERDICT'])
    print(json.dumps(doc['C_redistribution'], indent=1))
    print(len(doc['D_labelling_mismatches']), 'labelling mismatches')
