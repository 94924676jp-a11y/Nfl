#!/usr/bin/env python3.12
"""Week-4 Early Only postgame grading against the EXACT locked state. Results never flow backwards.

    python3.12 nfl/postgame/classic_week.py ingest  --kind NFL_PLAYER_WEEK --file stats_player_week_2026.csv \
        --source "nflverse-data release player_stats" --captured-at 2026-10-05T09:00:00Z
    python3.12 nfl/postgame/classic_week.py ingest  --kind DK_STANDINGS --file contest-standings-196208416.csv \
        --source "DraftKings contest standings export, downloaded by the owner" --captured-at ...
    python3.12 nfl/postgame/classic_week.py grade

THE LOCK. Every pregame object is read with `git show <LOCK_COMMIT>:<path>` -- never from the working
tree -- and the upload must hash to LOCK_UPLOAD_SHA256. A regrade therefore cannot see a post-lock edit.

OWN DATA FIRST. Player truth is computed from box-score components with the same scorer the projection
used (`nfl.product.dk_scoring`), plus the realised-only rules (two-point conversions, return TDs, the DST
table). DraftKings' own FPTS (from the owner's standings export) is the cross-check, and for a DST it is
the fallback when the defensive components are not held, labelled DK_REPORTED. FantasyCruncher is never
read here.

REFUSALS. A results file that does not cover all 16 clubs, carries blank numeric cells, lacks a column,
or changed bytes since ingest is refused by name: a game missing from the feed would otherwise grade
every player in it as a zero.

ONE SLATE. Eight games, correlated within game. Calibration figures are reported with their counts and
accumulate in the ledger; one Sunday does not establish calibration, skill, or luck.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import math
import pathlib
import re
import shutil
import subprocess
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

SLATE = '2026W4'
SEASON, WEEK = 2026, 4
LOCK_COMMIT = '039cfd0e'
LOCK_UPLOAD_SHA256 = 'bf50aaeefc0788063e77c69cc85450c54c5c22720f5fad3b4be02c370ca06899'
SAL = 'nfl/dfs/salaries'
RAW = _REPO / 'nfl/postgame/raw' / SLATE
OUT = _REPO / SAL / 'postgame'
PROVENANCE = RAW / 'PROVENANCE.jsonl'
CONTESTS = {'196208416': 'MAX150', '196208417': 'MAX20', '196208418': 'MAX3'}
KINDS = ('NFL_PLAYER_WEEK', 'NFL_GAMES', 'DK_STANDINGS')
#: nflverse stats_player_week columns graded for skill players
SKILL_COLS = ('completions', 'attempts', 'passing_yards', 'passing_tds', 'passing_interceptions', 'carries',
              'rushing_yards', 'rushing_tds', 'receptions', 'targets', 'receiving_yards', 'receiving_tds',
              'rushing_fumbles_lost', 'receiving_fumbles_lost', 'sack_fumbles_lost')
OPTIONAL_COLS = ('passing_2pt_conversions', 'rushing_2pt_conversions', 'receiving_2pt_conversions',
                 'special_teams_tds')
DST_COLS = ('def_sacks', 'def_interceptions', 'fumble_recovery_opp', 'def_tds', 'def_safeties')
FLEX = {'RB', 'WR', 'TE'}
SLOTS = (('QB', {'QB'}), ('RB', {'RB'}), ('RB', {'RB'}), ('WR', {'WR'}), ('WR', {'WR'}), ('WR', {'WR'}),
         ('TE', {'TE'}), ('FLEX', FLEX), ('DST', {'DST'}))


# ------------------------------------------------------------------------------------------- lock
def _git(path):
    p = subprocess.run(['git', 'show', f'{LOCK_COMMIT}:{path}'], cwd=_REPO, capture_output=True)
    if p.returncode:
        raise FileNotFoundError(f'{path} not in lock commit {LOCK_COMMIT}')
    return p.stdout


def locked() -> Outcome:
    f = lambda n: f'{SAL}/DK_{SLATE}_EARLY_{n}'  # noqa: E731
    up = _git(f('FINAL_DK_UPLOAD_POST_INACTIVES.csv'))
    if hashlib.sha256(up).hexdigest() != LOCK_UPLOAD_SHA256:
        return Outcome.fail('LOCK_UPLOAD_HASH_MISMATCH', 'the lock commit does not hold the submitted upload')
    st, proj = json.loads(_git(f('STATE.json'))), json.loads(_git(f('PROJ.json')))
    seal, port = json.loads(_git(f('SEAL.json'))), json.loads(_git(f('PORTFOLIOS.json')))
    if seal['projection_sha256'] != hashlib.sha256(_git(f('PROJ.json'))).hexdigest():
        return Outcome.fail('LOCK_SEAL_MISMATCH', 'the sealed projection is not the locked projection')
    if seal['written_at'] >= seal['kickoff_utc']:
        return Outcome.fail('LOCK_SEAL_AFTER_KICKOFF', f"seal {seal['written_at']} is not before {seal['kickoff_utc']}")
    draws = json.loads(_git(f('DRAWS.json')))['draws']
    rows = list(csv.reader(io.StringIO(up.decode(), newline='')))
    return Outcome.ok('LOCK_LOADED', {'state': st, 'proj': proj['rows'], 'draws': draws, 'port': port, 'seal': seal,
                                      'upload_header': rows[0], 'upload': rows[1:]},
                      f'lock {LOCK_COMMIT}, upload {LOCK_UPLOAD_SHA256[:12]}, seal {seal["written_at"]}')


# ------------------------------------------------------------------------------------------ ingest
def ingest(kind, src_file, source, captured_at, event_time=None) -> Outcome:
    if kind not in KINDS:
        return Outcome.fail('INGEST_KIND_UNKNOWN', f'{kind} not in {KINDS}')
    src = pathlib.Path(src_file)
    if not src.exists() or src.stat().st_size == 0:
        return Outcome.blocked('INGEST_FILE_EMPTY', f'{src} is missing or empty', cause=Cause.EMPTY_INPUT)
    RAW.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(src.read_bytes()).hexdigest()
    dst = RAW / f'{kind}.{sha[:16]}{"".join(src.suffixes) or ".csv"}'
    if not dst.exists():
        shutil.copy2(src, dst)
        dst.chmod(0o444)
    rel = str(dst.relative_to(_REPO)) if dst.is_relative_to(_REPO) else str(dst)
    rec = {'kind': kind, 'file': rel, 'sha256': sha, 'source': source,
           'captured_at': captured_at, 'event_time': event_time or f'{SEASON} week {WEEK} Early Only (1:00 PM ET)',
           'ingested_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'original_name': src.name,
           'slate_scope': SLATE + ' Early Only 8 games'}
    with PROVENANCE.open('a') as fh:
        fh.write(json.dumps(rec) + '\n')
    return Outcome.ok('INGESTED', rec, f'{kind} {sha[:12]} -> {dst.name}')


def _ingested(kind):
    if not PROVENANCE.exists():
        return []
    out = []
    for ln in PROVENANCE.read_text().splitlines():
        r = json.loads(ln)
        if r['kind'] != kind:
            continue
        p = pathlib.Path(r['file']) if pathlib.Path(r['file']).is_absolute() else _REPO / r['file']
        if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest() != r['sha256']:
            raise SystemExit(f"REFUSED: {r['file']} changed or vanished since ingest")
        out.append((p, r))
    return out


def _read_csv(p):
    raw = p.read_bytes()
    if p.suffix == '.gz' or raw[:2] == b'\x1f\x8b':
        raw = gzip.decompress(raw)
    return list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline='')))


# --------------------------------------------------------------------------------------- actuals
def player_week(lock) -> Outcome:
    got = _ingested('NFL_PLAYER_WEEK')
    if not got:
        return Outcome.blocked('ACTUALS_NOT_INGESTED', 'no NFL_PLAYER_WEEK file ingested for this slate', cause=Cause.DATA)
    p, rec = got[-1]
    rows = _read_csv(p)
    if not rows:
        return Outcome.blocked('ACTUALS_EMPTY', f'{p.name} parsed to zero rows', cause=Cause.EMPTY_INPUT)
    team_col = 'team' if 'team' in rows[0] else 'recent_team' if 'recent_team' in rows[0] else None
    missing = [c for c in SKILL_COLS + ('player_id', 'season', 'week', 'position') if c not in rows[0]] + \
              ([] if team_col else ['team'])
    if missing:
        return Outcome.blocked('ACTUALS_SCHEMA_MISMATCH', f'{p.name} lacks {missing}', cause=Cause.DATA)
    clubs = {c for g in lock['state']['games'].values() for c in (g['away'], g['home'])}
    alias = {'LAR': 'LA', 'JAC': 'JAX'}
    sel = [r for r in rows if r['season'] == str(SEASON) and r['week'] == str(WEEK)
           and alias.get(r[team_col], r[team_col]) in clubs]
    have = {alias.get(r[team_col], r[team_col]) for r in sel}
    if have != clubs:
        return Outcome.blocked('ACTUALS_GAMES_MISSING', f'{p.name} has no week-{WEEK} rows for {sorted(clubs - have)}',
                               cause=Cause.DATA, missing=sorted(clubs - have))
    blanks = collections.Counter(c for r in sel for c in SKILL_COLS if r.get(c) in (None, '', 'NA'))
    if blanks:
        return Outcome.blocked('ACTUALS_NUMERIC_CELL_BLANK', f'blank skill cells: {dict(blanks)}', cause=Cause.DATA)
    by_id = {}
    for r in sel:
        r['_team'] = alias.get(r[team_col], r[team_col])
        for c in SKILL_COLS + OPTIONAL_COLS + DST_COLS:
            if c in r:
                r[c] = None if r[c] in ('', 'NA', None) else float(r[c])
        by_id[r['player_id']] = r
    return Outcome.ok('ACTUALS_LOADED', by_id, f'{len(by_id)} player rows, 16/16 clubs', provenance=rec,
                      optional_present=[c for c in OPTIONAL_COLS if c in rows[0]],
                      dst_cols_present=[c for c in DST_COLS if c in rows[0]])


def game_scores(lock) -> Outcome:
    got = _ingested('NFL_GAMES')
    if not got:
        return Outcome.blocked('GAMES_NOT_INGESTED', 'no NFL_GAMES file (final scores) ingested', cause=Cause.DATA)
    p, rec = got[-1]
    alias = {'LAR': 'LA', 'JAC': 'JAX'}
    want = {(g['away'], g['home']): gid for gid, g in lock['state']['games'].items()}
    out = {}
    for r in _read_csv(p):
        k = (alias.get(r.get('away_team'), r.get('away_team')), alias.get(r.get('home_team'), r.get('home_team')))
        if k in want and str(r.get('season')) == str(SEASON) and str(r.get('week')) == str(WEEK):
            if r.get('away_score') in ('', 'NA', None) or r.get('home_score') in ('', 'NA', None):
                return Outcome.blocked('GAMES_SCORE_BLANK', f'{k} has no final score yet', cause=Cause.DATA)
            out[want[k]] = {'away': k[0], 'home': k[1], 'away_score': int(float(r['away_score'])),
                            'home_score': int(float(r['home_score']))}
    if len(out) != len(want):
        return Outcome.blocked('GAMES_MISSING', f'{sorted(set(want.values()) - set(out))} absent', cause=Cause.DATA)
    return Outcome.ok('GAMES_LOADED', out, f'{len(out)} final scores', provenance=rec)


_SLOT_RE = re.compile(r'\b(QB|RB|WR|TE|FLEX|DST)\s+')


def parse_lineup(s):
    """'QB Josh Allen RB A RB B ... DST Bears' -> [(slot, name)]."""
    parts = _SLOT_RE.split(' ' + (s or '').strip())
    toks = [x.strip() for x in parts if x.strip()]
    return [(toks[i], toks[i + 1]) for i in range(0, len(toks) - 1, 2)]


def standings(lock) -> Outcome:
    got = _ingested('DK_STANDINGS')
    if not got:
        return Outcome.blocked('STANDINGS_NOT_INGESTED', 'no DraftKings standings export ingested', cause=Cause.DATA)
    ours = {r[0]: r[2] for r in lock['upload']}
    contests, players, recs = {}, {}, []
    for p, rec in got:
        rows = _read_csv(p)
        need = ('Rank', 'EntryId', 'Points', 'Lineup')
        if not rows or any(c not in rows[0] for c in need):
            return Outcome.blocked('STANDINGS_SCHEMA', f'{p.name} lacks {need}', cause=Cause.DATA)
        ent = [r for r in rows if r.get('EntryId')]
        cids = {ours[r['EntryId']] for r in ent if r['EntryId'] in ours}
        if len(cids) != 1:
            return Outcome.blocked('STANDINGS_CONTEST_UNKNOWN', f'{p.name} holds our entries for {sorted(cids) or "no"} contest(s)',
                                   cause=Cause.DATA)
        cid = cids.pop()
        contests[cid] = {'file': rec['file'], 'n_entries': len(ent),
                         'entries': [{'rank': int(r['Rank']), 'entry_id': r['EntryId'], 'name': r.get('EntryName'),
                                      'points': float(r['Points']), 'lineup': parse_lineup(r['Lineup']),
                                      'ours': r['EntryId'] in ours} for r in ent]}
        for r in rows:
            if r.get('Player') and r.get('FPTS') not in (None, ''):
                players[r['Player'].strip()] = {'fpts': float(r['FPTS']), 'pct_drafted': r.get('%Drafted'),
                                                'roster_position': r.get('Roster Position')}
        recs.append(rec)
    return Outcome.ok('STANDINGS_LOADED', {'contests': contests, 'players': players},
                      f'{len(contests)} contest(s): ' + ', '.join(f'{CONTESTS.get(c, c)} {v["n_entries"]}' for c, v in contests.items()),
                      provenance=recs)


def actual_points(lock, pw, games, stand):
    """dk_id -> {'actual', 'basis', components...}; never zero-for-missing."""
    from nfl.product import dk_scoring as DKS
    st = lock['state']['players']
    gs = {(g['away'], g['home']): g for g in (games or {}).values()}
    dkf = (stand or {}).get('players') or {}
    team_def = collections.defaultdict(lambda: collections.Counter())
    for r in (pw or {}).values():
        for c in DST_COLS:
            if r.get(c) is not None:
                team_def[r['_team']][c] += r[c]
        if r.get('special_teams_tds') is not None and r.get('position') not in ('QB', 'RB', 'WR', 'TE'):
            team_def[r['_team']]['st_tds'] += r['special_teams_tds']
    out = {}
    for dk, p in st.items():
        rec = {'name': p['name'], 'team': p['team'], 'position': p['position']}
        if p['position'] == 'DST':
            g = next((v for k, v in gs.items() if p['team'] in k), None)
            td = team_def.get(p['team'])
            if g and td and all(c in td for c in ('def_sacks', 'def_interceptions')):
                pa = g['home_score'] if g['away'] == p['team'] else g['away_score']
                rec.update(actual=round(DKS.dst_points(points_allowed=pa, sacks=td['def_sacks'], ints=td['def_interceptions'],
                                                       fumble_recoveries=td.get('fumble_recovery_opp', 0),
                                                       tds=td.get('def_tds', 0) + td.get('st_tds', 0),
                                                       safeties=td.get('def_safeties', 0)), 2),
                           basis='COMPONENTS (blocked kicks and 2-pt returns not in the feed)', points_allowed=pa)
            elif p['name'] in dkf:
                rec.update(actual=dkf[p['name']]['fpts'], basis='DK_REPORTED')
            else:
                rec.update(actual=None, basis='NOT_GRADED: no DST components and no DK standings')
        else:
            r = (pw or {}).get(p.get('gsis_id') or '')
            if r is not None:
                fl = r['rushing_fumbles_lost'] + r['receiving_fumbles_lost'] + r['sack_fumbles_lost']
                base = float(DKS.skill_points(1, pass_yds=[r['passing_yards']], pass_td=[r['passing_tds']],
                                              ints=[r['passing_interceptions']], rush_yds=[r['rushing_yards']],
                                              rush_td=[r['rushing_tds']], rec=[r['receptions']], rec_yds=[r['receiving_yards']],
                                              rec_td=[r['receiving_tds']], fumbles_lost=[fl])[0])
                two = sum((r.get(c) or 0) for c in ('passing_2pt_conversions', 'rushing_2pt_conversions', 'receiving_2pt_conversions'))
                extra = DKS.realised_extra_points(two_pt=two, return_td=r.get('special_teams_tds') or 0)
                rec.update(actual=round(base + extra, 2), basis='COMPONENTS',
                           targets=r['targets'], receptions=r['receptions'], rec_yds=r['receiving_yards'],
                           carries=r['carries'], rush_yds=r['rushing_yards'], pass_att=r['attempts'],
                           pass_yds=r['passing_yards'], tds=r['passing_tds'] + r['rushing_tds'] + r['receiving_tds'])
            elif p['current_availability']['status'] in ('CONFIRMED_INACTIVE', 'REPORTED_INACTIVE_HIGH_CONFIDENCE',
                                                          'REPORTED_INACTIVE_OFFICIAL_RELEASE_CITED', 'REPORTED_OUT_UNVERIFIED'):
                rec.update(actual=0.0, basis='INACTIVE_AT_LOCK_AND_NO_STAT_ROW')
            elif pw is not None:
                rec.update(actual=0.0, basis='NO_STAT_ROW_IN_A_COMPLETE_FEED (did not record a stat)')
            elif p['name'] in dkf:
                rec.update(actual=dkf[p['name']]['fpts'], basis='DK_REPORTED')
            else:
                rec.update(actual=None, basis='NOT_GRADED')
        if p['name'] in dkf and rec.get('actual') is not None and rec['basis'] != 'DK_REPORTED':
            rec['dk_reported'] = dkf[p['name']]['fpts']
            rec['dk_reconciles'] = abs(dkf[p['name']]['fpts'] - rec['actual']) < 0.05
        if p['name'] in dkf:
            rec['pct_drafted'] = dkf[p['name']]['pct_drafted']
        out[dk] = rec
    return out


# ------------------------------------------------------------------------------------------ grading
def _crps(x, y):
    """Sample CRPS: E|X-y| - 0.5 E|X-X'|, with E|X-X'| from the sorted-sample identity."""
    x = np.sort(np.asarray(x, dtype=float))
    n = len(x)
    i = np.arange(1, n + 1)
    e_xx = 2.0 * np.sum((2 * i - n - 1) * x) / (n * n)
    return float(np.mean(np.abs(x - y)) - 0.5 * e_xx)


def _spearman(a, b):
    ra, rb = np.argsort(np.argsort(a)), np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1]) if len(a) > 2 else None


def grade_players(lock, act):
    st, proj, draws = lock['state']['players'], lock['proj'], lock['draws']
    from nfl.tools import showdown_draws as SD
    rows = []
    for dk, a in act.items():
        if a.get('actual') is None:
            continue
        p, r = st[dk], proj.get(dk) or {}
        key = SD.S.player_key(p['name'], p['team'])
        d = np.asarray(draws.get(key) or [], dtype=float)
        mean = r.get('dk_points') if r else None
        if mean is None and len(d):
            mean = float(d.mean())
        if mean is None or (mean < 0.5 and a['actual'] < 0.5):
            continue
        row = {'dk_id': dk, 'player': p['name'], 'team': p['team'], 'pos': p['position'], 'proj': round(mean, 2),
               'actual': a['actual'], 'error': round(a['actual'] - mean, 2), 'basis': a['basis']}
        if len(d):
            u = float((d < a['actual']).mean() + 0.5 * (d == a['actual']).mean())
            row.update(sim_mean=round(float(d.mean()), 2), pit=round(u, 4),
                       p10=round(float(np.percentile(d, 10)), 2), p50=round(float(np.percentile(d, 50)), 2),
                       p90=round(float(np.percentile(d, 90)), 2), p95=round(float(np.percentile(d, 95)), 2),
                       in_p10_p90=bool(np.percentile(d, 10) <= a['actual'] <= np.percentile(d, 90)),
                       above_p90=bool(a['actual'] > np.percentile(d, 90)),
                       crps=round(_crps(d, a['actual']), 3))
        for f, pf in (('targets', 'targets'), ('carries', 'carries'), ('pass_att', 'pass_attempts'), ('receptions', 'receptions'),
                      ('rec_yds', 'rec_yards'), ('rush_yds', 'rush_yards'), ('pass_yds', 'pass_yards')):
            if a.get(f) is not None and r.get(pf) is not None:
                row[f'{f}_proj'], row[f'{f}_actual'] = round(r[pf], 2), a[f]
        rows.append(row)
    summ = {}
    for pos in sorted({r['pos'] for r in rows}) + ['ALL']:
        g = [r for r in rows if pos == 'ALL' or r['pos'] == pos]
        e = np.array([r['error'] for r in g])
        pits = [r['pit'] for r in g if 'pit' in r]
        summ[pos] = {'n': len(g), 'mae': round(float(np.abs(e).mean()), 2), 'rmse': round(float(np.sqrt((e ** 2).mean())), 2),
                     'bias_actual_minus_proj': round(float(e.mean()), 2),
                     'spearman_proj_vs_actual': _spearman([r['proj'] for r in g], [r['actual'] for r in g]),
                     'share_in_p10_p90': round(float(np.mean([r['in_p10_p90'] for r in g if 'in_p10_p90' in r])), 3) if pits else None,
                     'share_above_p90': round(float(np.mean([r['above_p90'] for r in g if 'above_p90' in r])), 3) if pits else None,
                     'NOMINAL': {'in_p10_p90': 0.8, 'above_p90': 0.1},
                     'pit_deciles': np.histogram(pits, bins=10, range=(0, 1))[0].tolist() if pits else None,
                     'mean_crps': round(float(np.mean([r['crps'] for r in g if r.get('crps') is not None])), 3) if pits else None}
    return rows, summ


def grade_concentration(lock, prow):
    """The pre-lock audit's named defect: WR1/TE1 over-allocated, WR3/depth under-allocated."""
    st = lock['state']['players']
    out = collections.defaultdict(lambda: {'proj': 0.0, 'actual': 0.0, 'n': 0})
    for r in prow:
        if r.get('targets_proj') is None or r['pos'] not in ('WR', 'TE'):
            continue
        rk = st[r['dk_id']].get('depth_rank')
        band = f"{r['pos']}{rk if rk in (1, 2) else '3+'}"
        out[band]['proj'] += r['targets_proj']
        out[band]['actual'] += r['targets_actual']
        out[band]['n'] += 1
    res = {b: {**v, 'proj': round(v['proj'], 1), 'actual': round(v['actual'], 1),
               'actual_minus_proj_per_player': round((v['actual'] - v['proj']) / v['n'], 2) if v['n'] else None}
           for b, v in sorted(out.items())}
    named = {}
    for n in ('Kalif Raymond', 'Ryan Flournoy', 'Kayshon Boutte', 'Jaylin Noel', 'Malik McClain', 'CeeDee Lamb',
              'Parker Washington', 'Garrett Wilson', 'Mike Gesicki', 'Emeka Egbuka'):
        r = next((x for x in prow if x['player'] == n), None)
        if r and r.get('targets_proj') is not None:
            named[n] = {'targets_proj': r['targets_proj'], 'targets_actual': r['targets_actual']}
    return {'by_depth_band': res, 'named_in_prelock_audit': named,
            'READING': 'positive actual-minus-projected for WR3+ and negative for WR1/TE1 would confirm the pre-lock '
                       'finding on this slate; one slate is one observation'}


def optimal_lineup(lock, act):
    """Exact max-actual-points legal lineup over the locked pool (salary <= 50,000)."""
    st = lock['state']['players']
    pool = collections.defaultdict(list)
    for dk, a in act.items():
        if a.get('actual') is None:
            continue
        pool[st[dk]['position']].append((a['actual'], int(st[dk]['salary']) // 100, dk))
    cap = 500

    def best_k(items, kmax):
        # best[k][s] = (points, ids) choosing k players with salary units exactly s
        best = [[None] * (cap + 1) for _ in range(kmax + 1)]
        best[0][0] = (0.0, ())
        for pts, s, dk in sorted(items, key=lambda x: -x[0])[:60]:
            for k in range(kmax, 0, -1):
                row, prev = best[k], best[k - 1]
                for c in range(cap, s - 1, -1):
                    pv = prev[c - s]
                    if pv is not None and (row[c] is None or pv[0] + pts > row[c][0]):
                        row[c] = (pv[0] + pts, pv[1] + (dk,))
        return best

    def conv(a, b):
        c = [None] * (cap + 1)
        for i, x in enumerate(a):
            if x is None:
                continue
            for j in range(cap + 1 - i):
                y = b[j]
                if y is not None and (c[i + j] is None or x[0] + y[0] > c[i + j][0]):
                    c[i + j] = (x[0] + y[0], x[1] + y[1])
        return c

    bq, bd = best_k(pool['QB'], 1), best_k(pool['DST'], 1)
    br, bw, bt = best_k(pool['RB'], 3), best_k(pool['WR'], 4), best_k(pool['TE'], 2)
    qd = conv(bq[1], bd[1])
    top = None
    for r, w, t in ((2, 3, 2), (2, 4, 1), (3, 3, 1)):
        tot = conv(conv(qd, br[r]), conv(bw[w], bt[t]))
        cand = max((x for x in tot if x is not None), key=lambda x: x[0], default=None)
        if cand is not None and (top is None or cand[0] > top[0]):
            top = cand
    if top is None:
        return None
    return {'points': round(top[0], 2), 'players': [(st[k]['name'], st[k]['position'], st[k]['salary'], act[k]['actual']) for k in top[1]],
            'salary': sum(st[k]['salary'] for k in top[1])}


def grade_lineups(lock, act, stand):
    st = lock['state']['players']
    hdr = lock['upload_header']
    slots = [i for i, h in enumerate(hdr) if h in ('QB', 'RB', 'WR', 'TE', 'FLEX', 'DST')]
    res = collections.defaultdict(list)
    graded = all(act[k].get('actual') is not None for r in lock['upload'] for k in (r[i] for i in slots))
    sc = (stand or {}).get('contests') or {}
    rank_of = {e['entry_id']: e for c in sc.values() for e in c['entries']}
    for r in lock['upload']:
        ids = [r[i] for i in slots]
        pts = sum(act[k]['actual'] for k in ids) if graded else None
        e = rank_of.get(r[0])
        res[CONTESTS[r[2]]].append({'entry_id': r[0], 'points': round(pts, 2) if pts is not None else None,
                                    'dk_points': e['points'] if e else None, 'rank': e['rank'] if e else None,
                                    'field': sc.get(r[2], {}).get('n_entries'),
                                    'players': [(st[k]['name'], act[k].get('actual')) for k in ids]})
    out = {}
    for prof, ls in res.items():
        cid = next(c for c, p in CONTESTS.items() if p == prof)
        c = sc.get(cid)
        ls.sort(key=lambda x: (x['rank'] if x['rank'] is not None else 10 ** 9, -(x['points'] or 0)))
        winner = min(c['entries'], key=lambda e: e['rank']) if c else None
        best = ls[0]
        o = {'n': len(ls), 'best': best, 'median_points': float(np.median([x['points'] for x in ls])) if graded else None,
             'field_size': c['n_entries'] if c else 'STANDINGS_NOT_INGESTED'}
        if c:
            ranks = [x['rank'] for x in ls if x['rank']]
            o.update(best_rank=min(ranks), median_rank=float(np.median(ranks)),
                     share_top_1pct=round(sum(r_ <= c['n_entries'] * 0.01 for r_ in ranks) / len(ranks), 3),
                     share_top_10pct=round(sum(r_ <= c['n_entries'] * 0.10 for r_ in ranks) / len(ranks), 3),
                     share_top_20pct=round(sum(r_ <= c['n_entries'] * 0.20 for r_ in ranks) / len(ranks), 3),
                     winner={'points': winner['points'], 'lineup': winner['lineup'], 'ours': winner['ours']},
                     gap_to_first=round(winner['points'] - (best['dk_points'] or 0), 2))
            mine = {n for n, _ in best['players']}
            theirs = {n for _, n in winner['lineup']}
            o['what_kept_best_from_first'] = {'only_ours': sorted(mine - theirs), 'only_winner': sorted(theirs - mine),
                                              'shared': sorted(mine & theirs)}
        out[prof] = o
    return out, graded


def grade_exposures(lock, act):
    port = lock['port']
    rows = []
    for c in port['contests']:
        for _n, e in c['report']['player_exposure'].items():
            a = act.get(e['dk_id']) or {}
            pr = (lock['proj'].get(e['dk_id']) or {}).get('dk_points')
            rows.append({'contest': c['profile'], 'player': e.get('name') or _n, 'exposure': e['overall'], 'proj': pr,
                         'actual': a.get('actual'), 'pct_drafted': a.get('pct_drafted')})
    out = {}
    for prof in ('MAX150', 'MAX20', 'MAX3'):
        g = [r for r in rows if r['contest'] == prof and r['actual'] is not None and r['proj'] is not None]
        hi = [r for r in g if r['exposure'] >= 0.20]
        lo = [r for r in g if r['exposure'] < 0.20]
        f = lambda xs: round(float(np.mean([x['actual'] - x['proj'] for x in xs])), 2) if xs else None  # noqa: E731
        out[prof] = {'n_high': len(hi), 'high_exposure_mean_actual_minus_proj': f(hi), 'n_low': len(lo),
                     'low_exposure_mean_actual_minus_proj': f(lo),
                     'exposure_weighted_actual_minus_proj': round(float(sum(x['exposure'] * (x['actual'] - x['proj']) for x in g)
                                                                        / max(1e-9, sum(x['exposure'] for x in g))), 2) if g else None,
                     'THRESHOLD': '20% exposure, DECLARED reporting split'}
    return rows, out


def grade_stacks(lock, act):
    out = collections.defaultdict(lambda: {'n': 0, 'pts': []})
    for c in lock['port']['contests']:
        for lu in c['lineups']:
            qb = next(s for s in lu['slots'] if s['slot'] == 'QB')
            mates = sorted(s['name'] for s in lu['slots'] if s['team'] == qb['team'] and s['slot'] != 'QB')
            tot = sum((act.get(s['dk_id']) or {}).get('actual') or 0 for s in lu['slots'])
            k = (c['profile'], qb['name'], ' + '.join(mates) or '(naked)')
            out[k]['n'] += 1
            out[k]['pts'].append(tot)
    return sorted(({'contest': k[0], 'qb': k[1], 'stack': k[2], 'lineups': v['n'], 'mean_points': round(float(np.mean(v['pts'])), 2),
                    'max_points': round(max(v['pts']), 2)} for k, v in out.items()), key=lambda r: -r['max_points'])


def grade() -> Outcome:
    lo = locked()
    if lo.state.value != 'PASS':
        return lo
    lock = lo.value
    pw, gs, sd = player_week(lock), game_scores(lock), standings(lock)
    status = {k: f'{o.state.value}[{o.code}] {o.detail}' for k, o in (('player_week', pw), ('games', gs), ('standings', sd))}
    if pw.state.value != 'PASS' and sd.state.value != 'PASS':
        return Outcome.blocked('POSTGAME_NO_RESULTS', 'neither box-score components nor DraftKings standings are ingested: '
                               + '; '.join(status.values()), cause=Cause.DATA, inputs=status)
    act = actual_points(lock, pw.value if pw.state.value == 'PASS' else None,
                        gs.value if gs.state.value == 'PASS' else None, sd.value if sd.state.value == 'PASS' else None)
    prow, psum = grade_players(lock, act)
    lineups, all_graded = grade_lineups(lock, act, sd.value if sd.state.value == 'PASS' else None)
    erows, esum = grade_exposures(lock, act)
    doc = {'ARTIFACT': 'CLASSIC_POSTGAME', 'slate_id': SLATE, 'graded_at': dt.datetime.now(dt.timezone.utc).isoformat(),
           'LOCK': {'commit': LOCK_COMMIT, 'upload_sha256': LOCK_UPLOAD_SHA256, 'seal_written_at': lock['seal']['written_at'],
                    'kickoff_utc': lock['seal']['kickoff_utc']},
           'inputs': status, 'provenance': {k: o.evidence.get('provenance') for k, o in (('player_week', pw), ('games', gs), ('standings', sd))
                                            if o.state.value == 'PASS'},
           'actual_basis_counts': dict(collections.Counter(a['basis'] for a in act.values())),
           'dk_reconciliation': {'n_checked': sum(1 for a in act.values() if 'dk_reconciles' in a),
                                 'n_mismatch': sum(1 for a in act.values() if a.get('dk_reconciles') is False),
                                 'mismatches': [(a['name'], a['actual'], a['dk_reported']) for a in act.values() if a.get('dk_reconciles') is False][:30]},
           'players_summary': psum, 'concentration': grade_concentration(lock, prow) if pw.state.value == 'PASS' else 'NEEDS_BOX_SCORE_COMPONENTS',
           'lineups': lineups, 'all_173_graded': all_graded, 'exposures': esum, 'stacks_top': grade_stacks(lock, act)[:40],
           'optimal_lineup': optimal_lineup(lock, act),
           'ONE_SLATE': 'eight correlated games: these are observations for the ledger, not calibration or skill estimates'}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f'DK_{SLATE}_EARLY_POSTGAME.json').write_text(json.dumps(doc, indent=1, default=str))
    with (OUT / f'DK_{SLATE}_EARLY_POSTGAME_PLAYERS.csv').open('w', newline='') as fh:
        keys = sorted({k for r in prow for k in r})
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(prow)
    return Outcome.measured('POSTGAME_GRADED', {'n_players': len(prow)}, n_measured=len(prow), what='graded players',
                            detail=f"{len(prow)} players graded; all 173 lineups graded: {all_graded}; inputs: " + '; '.join(status.values()))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    i = sub.add_parser('ingest')
    i.add_argument('--kind', required=True, choices=KINDS)
    i.add_argument('--file', required=True)
    i.add_argument('--source', required=True)
    i.add_argument('--captured-at', required=True)
    i.add_argument('--event-time', default=None)
    sub.add_parser('grade')
    sub.add_parser('lock')
    a = ap.parse_args()
    if a.cmd == 'ingest':
        o = ingest(a.kind, a.file, a.source, a.captured_at, a.event_time)
    elif a.cmd == 'lock':
        o = locked()
        o = Outcome.ok(o.code, None, o.detail) if o.state.value == 'PASS' else o
    else:
        o = grade()
    print(f'{o.state.value}[{o.code}] {o.detail}')
    return 0 if o.state.value == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
