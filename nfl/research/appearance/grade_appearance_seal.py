#!/usr/bin/env python3.12
"""Grade appearance-successor PROSPECTIVE seals after the games. SHADOW_ONLY. Rules: the locked pre-registration
docs/NFL_APPEARANCE_SUCCESSOR_PREREGISTRATION.md (sections 4-5).

    python3.12 nfl/research/appearance/grade_appearance_seal.py \
        --seal nfl/prospective/appearance/APPEARANCE_SUCCESSOR_W5_SEAL.json [--seal ...W6...] \
        --panel <postgame USAGE_HISTORY json> --snaps <nflverse snap_counts_2026.csv[.gz]> \
        --crosswalk <players crosswalk csv[.gz]> --schedule <schedules csv.gz> [--out <grade json>]

REFUSES (named, never an empty success):
  SEAL_ABSENT / SEAL_EMPTY / SEAL_NOT_JSON      the file is not a seal
  SEAL_TAMPERED                                 seal_sha256 does not match the content (any edit after sealing)
  PREREG_MISMATCH                               the seal's prereg hash is not the locked pre-registration's
  SEAL_WRITTEN_AFTER_KICKOFF                    written_at is at/after a sealed game's kickoff (seal's own record or
                                                the schedule supplied to the grader)
  GAME_NOT_STARTED                              grading requested before a game's kickoff
  EMPTY_POSTGAME_PANEL / EMPTY_SNAPS / NO_GRADED_UNITS
A game the postgame panel does not carry is NOT_GRADABLE (never zero). An undressed sealed player is excluded and
counted (eligibility), never scored as zero.
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
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
PREREG = _REPO / 'docs/NFL_APPEARANCE_SUCCESSOR_PREREGISTRATION.md'
PREREG_LOCK = _REPO / 'nfl/prospective/appearance/APPEARANCE_SUCCESSOR_PREREG_LOCK.json'
#: Section 5 of the pre-registration. Not tunable here: changing one changes the evidence rule.
MIN_WEEKS, MIN_UNITS, MIN_CLUBS = 4, 1500, 25
Z_CLUB = 2.0
#: two-sided 97.5% Student-t quantiles by degrees of freedom (n_weeks - 1); published table values.
T975 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
        11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086,
        21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060, 26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042}
ET_NAME = 'America/New_York'


class GradeError(RuntimeError):
    def __init__(self, code, detail=''):
        self.code = code
        super().__init__(f'{code}: {detail}' if detail else code)


def canonical(doc):
    return json.dumps(doc, sort_keys=True, separators=(',', ':'), default=float)


def seal_hash(doc):
    return hashlib.sha256(canonical({k: v for k, v in doc.items() if k != 'seal_sha256'}).encode()).hexdigest()


def _open_text(p):
    p = pathlib.Path(p)
    return gzip.open(p, 'rt', newline='') if p.suffix == '.gz' else open(p, newline='')


def kickoff_utc(gameday, gametime):
    from zoneinfo import ZoneInfo
    t = dt.datetime.strptime(f'{gameday} {gametime}', '%Y-%m-%d %H:%M').replace(tzinfo=ZoneInfo(ET_NAME))
    return t.astimezone(dt.timezone.utc)


def load_seal(path, prereg=PREREG, prereg_lock=PREREG_LOCK):
    p = pathlib.Path(path)
    if not p.exists():
        raise GradeError('SEAL_ABSENT', str(p))
    raw = p.read_text()
    if not raw.strip():
        raise GradeError('SEAL_EMPTY', str(p))
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as e:
        raise GradeError('SEAL_NOT_JSON', str(e)) from e
    if not isinstance(doc, dict) or doc.get('seal_sha256') != seal_hash(doc):
        raise GradeError('SEAL_TAMPERED', f'{p.name}: recorded {doc.get("seal_sha256") if isinstance(doc, dict) else None}')
    lock = json.loads(pathlib.Path(prereg_lock).read_text()) if pathlib.Path(prereg_lock).exists() else {}
    want = lock.get('prereg_sha256')
    have = (doc.get('prereg') or {}).get('sha256')
    cur = hashlib.sha256(pathlib.Path(prereg).read_bytes()).hexdigest() if pathlib.Path(prereg).exists() else None
    if not want or have != want or cur != want:
        raise GradeError('PREREG_MISMATCH', f'seal {have} lock {want} file {cur}')
    written = dt.datetime.fromisoformat(doc['written_at'])
    first = dt.datetime.fromisoformat(doc['first_kickoff_utc'])
    if written >= first:
        raise GradeError('SEAL_WRITTEN_AFTER_KICKOFF', f'written_at {written.isoformat()} >= first kickoff {first.isoformat()}')
    for gid, g in (doc.get('games') or {}).items():
        if written >= dt.datetime.fromisoformat(g['kickoff_utc']):
            raise GradeError('SEAL_WRITTEN_AFTER_KICKOFF', f'{gid}: written_at {written.isoformat()} >= {g["kickoff_utc"]}')
    return doc


def schedule_kickoffs(path, season, week):
    out = {}
    with _open_text(path) as fh:
        for r in csv.DictReader(fh):
            if r.get('season') == str(season) and r.get('week') == str(week) and r.get('gameday') and r.get('gametime'):
                out[r['game_id']] = kickoff_utc(r['gameday'], r['gametime'])
    return out


def dressed_from_snaps(snaps_path, crosswalk_path, season):
    """{(club, week): {gsis}} -- present in the nflverse snap-count file (offense or special teams)."""
    with _open_text(crosswalk_path) as fh:
        cw = {r['pfr_id']: r['gsis_id'] for r in csv.DictReader(fh) if r.get('pfr_id') and r.get('gsis_id')}
    out = collections.defaultdict(set)
    with _open_text(snaps_path) as fh:
        for r in csv.DictReader(fh):
            if str(r.get('season')) != str(season) or (r.get('game_type') or 'REG') != 'REG':
                continue
            g = cw.get(r.get('pfr_player_id'))
            if g:
                out[(r['team'], int(r['week']))].add(g)
    if not out:
        raise GradeError('EMPTY_SNAPS', str(snaps_path))
    return out


def _clip(p, n):
    f = 0.5 / n
    return min(max(float(p), f), 1.0 - f)


def _crps_hist(hist, y):
    ks = sorted(int(k) for k in hist)
    n = float(sum(hist.values()))
    out, cum = 0.0, 0.0
    for k in range(min(ks[0], int(y)), max(ks[-1], int(y)) + 1):
        cum += hist.get(str(k), 0) / n
        out += (cum - (1.0 if y <= k else 0.0)) ** 2
    return out


def grade_units(seal, panel, dressed, kickoffs, now):
    season, week, n = seal['season'], seal['week'], seal['n_sims']
    written = dt.datetime.fromisoformat(seal['written_at'])
    units, counts = [], collections.Counter()
    for gid, g in seal['games'].items():
        if g.get('state') != 'SEALED':
            counts['GAME_NOT_SEALED'] += 1
            continue
        k = kickoffs.get(gid)
        if k is None:
            counts['GAME_NOT_IN_SCHEDULE'] += 1
            continue
        if written >= k:
            raise GradeError('SEAL_WRITTEN_AFTER_KICKOFF', f'{gid}: schedule kickoff {k.isoformat()} <= written_at')
        if now < k:
            raise GradeError('GAME_NOT_STARTED', f'{gid} kicks off {k.isoformat()}')
        for u in g['units']:
            club = u['club']
            if str(week) not in ((panel['teams'].get(club) or {}).get(str(season)) or {}):
                counts['NOT_GRADABLE_GAME_MISSING_FROM_POSTGAME_PANEL'] += 1
                continue
            if u['gsis'] not in dressed.get((club, week), set()):
                counts['EXCLUDED_NOT_DRESSED'] += 1
                continue
            row = ((panel['players'].get(u['gsis']) or {}).get(str(season)) or {}).get(str(week)) or {}
            if row and row.get('team') not in (None, club):
                counts['EXCLUDED_ROW_FOR_OTHER_CLUB'] += 1
                continue
            y = float(row.get(u['field']) or 0.0)
            y0 = 1.0 if y == 0 else 0.0
            x = {'week': week, 'club': club, 'game_id': gid, 'gsis': u['gsis'], 'position': u['position'],
                 'field': u['field'], 'rank_table': u['rank_table'], 'h': u['h_last3_present'], 'y': y, 'y0': y0}
            for arm, col in (('DRAW_CURRENT', 'P0_draws_current'), ('DRAW_SUCCESSOR', 'P0_draws_successor'),
                             ('PROJ_CURRENT', 'P0_projection_current'), ('PROJ_CANDIDATE', 'P0_projection_candidate')):
                p = _clip(u[col], n)
                x[f'brier_{arm}'] = (p - y0) ** 2
                x[f'log_{arm}'] = -(y0 * math.log(p) + (1 - y0) * math.log(1 - p))
            if y > 0:
                for arm, col in (('CURRENT', 'hist_current'), ('SUCCESSOR', 'hist_successor')):
                    hp = {kk: v for kk, v in u[col].items() if int(kk) > 0}
                    x[f'ccrps_{arm}'] = _crps_hist(hp, y) if hp else float('nan')
            x['dk_zero_successor'] = u['P_dk_zero_successor']
            units.append(x)
            counts['GRADED'] += 1
    return units, counts


def _blocked(vals, blocks):
    by = collections.defaultdict(list)
    for v, b in zip(vals, blocks):
        if not math.isnan(v):
            by[b].append(v)
    means = [sum(v) / len(v) for v in by.values() if v]
    nb = len(means)
    m = sum(means) / nb if nb else float('nan')
    se = (float(np.std(means, ddof=1)) / math.sqrt(nb)) if nb > 1 else float('nan')
    return {'mean_of_block_means': m, 'se': se, 'n_blocks': nb, 'z': (m / se if se and se > 0 else None)}


def _paired(units, a, b, key='brier'):
    d = [u[f'{key}_{a}'] - u[f'{key}_{b}'] for u in units if f'{key}_{a}' in u and f'{key}_{b}' in u]
    us = [u for u in units if f'{key}_{a}' in u and f'{key}_{b}' in u]
    dd = [x for x in d if not math.isnan(x)]
    return {'n_units': len(d), 'pooled': (sum(dd) / len(dd) if dd else float('nan')), 'n_nan_excluded': len(d) - len(dd),
            'week_blocked': _blocked(d, [u['week'] for u in us]),
            'club_blocked': _blocked(d, [u['club'] for u in us])}


def evaluate(units):
    weeks = sorted({u['week'] for u in units})
    clubs = sorted({u['club'] for u in units})
    prim = _paired(units, 'DRAW_CURRENT', 'DRAW_SUCCESSOR')
    pos = [u for u in units if u['y'] > 0]
    pc = _paired(pos, 'CURRENT', 'SUCCESSOR', key='ccrps')
    r1 = _paired([u for u in units if u['rank_table'] == 1], 'DRAW_CURRENT', 'DRAW_SUCCESSOR')
    sample = {'n_weeks': len(weeks), 'n_units': len(units), 'n_clubs': len(clubs),
              'minimum': {'weeks': MIN_WEEKS, 'units': MIN_UNITS, 'clubs': MIN_CLUBS}}
    enough = len(weeks) >= MIN_WEEKS and len(units) >= MIN_UNITS and len(clubs) >= MIN_CLUBS
    out = {'sample': sample, 'PRIMARY_draw_zero_brier_current_minus_successor': prim,
           'POSITIVE_COUNT_conditional_crps_current_minus_successor': pc,
           'RANK1_draw_zero_brier_current_minus_successor': r1,
           'SECONDARY_projection_brier_current_minus_candidate': _paired(units, 'PROJ_CURRENT', 'PROJ_CANDIDATE'),
           'SECONDARY_log_draw_current_minus_successor': _paired(units, 'DRAW_CURRENT', 'DRAW_SUCCESSOR', key='log')}
    if not enough:
        out['VERDICT'] = 'INSUFFICIENT_SAMPLE'
        return out
    wb, cb = prim['week_blocked'], prim['club_blocked']
    if wb['n_blocks'] - 1 not in T975:
        raise GradeError('T_CRITICAL_UNTABULATED', f'df={wb["n_blocks"] - 1}')
    tcrit = T975[wb['n_blocks'] - 1]
    checks = {
        'primary_club_blocked_z_gt_2': bool(cb['z'] is not None and cb['z'] > Z_CLUB),
        'primary_week_blocked_t_gt_tcrit': bool(wb['z'] is not None and wb['mean_of_block_means'] > 0 and wb['z'] > tcrit),
        'positive_count_not_worse_by_2_club_se': bool(pc['club_blocked']['mean_of_block_means']
                                                      >= -2 * pc['club_blocked']['se']),
        'rank1_not_worse_by_2_club_se': bool(r1['club_blocked']['mean_of_block_means'] >= -2 * r1['club_blocked']['se'])}
    out['t_critical_week_blocked'] = tcrit
    out['checks'] = checks
    out['VERDICT'] = 'PASS' if all(checks.values()) else 'FAIL'
    return out


def grade(seal_paths, panel, dressed, schedule_path, now=None, prereg=PREREG, prereg_lock=PREREG_LOCK):
    now = now or dt.datetime.now(dt.timezone.utc)
    if not panel or not panel.get('players') or not panel.get('teams'):
        raise GradeError('EMPTY_POSTGAME_PANEL')
    if not dressed:
        raise GradeError('EMPTY_SNAPS')
    if not seal_paths:
        raise GradeError('SEAL_ABSENT', 'no seal given')
    all_units, per_seal = [], {}
    for sp in seal_paths:
        seal = load_seal(sp, prereg, prereg_lock)
        ks = schedule_kickoffs(schedule_path, seal['season'], seal['week'])
        units, counts = grade_units(seal, panel, dressed, ks, now)
        per_seal[str(sp)] = {'week': seal['week'], 'seal_sha256': seal['seal_sha256'],
                             'written_at': seal['written_at'], 'counts': dict(counts)}
        all_units += units
    if not all_units:
        raise GradeError('NO_GRADED_UNITS', json.dumps(per_seal))
    res = evaluate(all_units)
    return {'ARTIFACT': 'APPEARANCE_SUCCESSOR_GRADE', 'STATUS': 'SHADOW_ONLY', 'graded_at': now.isoformat(),
            'prereg_sha256': json.loads(pathlib.Path(prereg_lock).read_text())['prereg_sha256'],
            'seals': per_seal, **res,
            'EVIDENCE_CLASS': 'PROSPECTIVE (sealed before kickoff, graded after). A verdict exists only when the '
                              'pre-registered minimum sample is met; one look.'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seal', action='append', required=True)
    ap.add_argument('--panel', required=True)
    ap.add_argument('--snaps', required=True)
    ap.add_argument('--crosswalk', required=True)
    ap.add_argument('--schedule', required=True)
    ap.add_argument('--out')
    a = ap.parse_args()
    panel = json.loads(pathlib.Path(a.panel).read_text())
    seals = [load_seal(s) for s in a.seal]
    dressed = dressed_from_snaps(a.snaps, a.crosswalk, seals[0]['season'])
    doc = grade(a.seal, panel, dressed, a.schedule)
    if a.out:
        out = pathlib.Path(a.out)
        with open(out, 'x') as fh:          # write-once: a verdict is never silently re-computed over
            fh.write(json.dumps(doc, indent=1, default=float))
        print(f'VERIFIED {out} ({out.stat().st_size} bytes, sha256 {hashlib.sha256(out.read_bytes()).hexdigest()})')
    print(json.dumps({'VERDICT': doc['VERDICT'], 'sample': doc['sample']}, indent=1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
