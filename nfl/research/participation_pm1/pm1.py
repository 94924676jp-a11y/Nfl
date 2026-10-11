#!/usr/bin/env python3.12
"""PM-1: the participation table for injury-report players, fitted on 2016-2023, judged on 2024-2025 (PREREG_PM1).

    python3.12 nfl/research/participation_pm1/pm1.py            # fit, freeze the table, then evaluate held-out

Every definition is the pre-registration's (PREREG_PM1_PARTICIPATION.md, committed d3c0f775 before any download).
The table is written from the fit seasons BEFORE a held-out row is read; the evaluation then reads the frozen table.

Outputs (this directory):
  PM1_TABLE.json        per-cell P(no participation), the workload-share distribution r/r0 (101-point quantile grid)
                        and P(early exit), with n, pooling level and the parent each cell was shrunk toward
  PM1_EVALUATION.json   H-a, H-b and H-c on 2024-2025 with club-week cluster-bootstrap intervals, and the verdict
  PM1_UNITS_SUMMARY.json counts of units, exclusions and NO_BASELINE by season (never hidden)
"""
from __future__ import annotations

import collections
import csv
import gzip
import io
import json
import math
import pathlib
import random
import statistics
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
HERE = pathlib.Path(__file__).parent
VINTAGE = _REPO / 'nfl/vintage'
FIT, HELD = tuple(range(2016, 2024)), (2024, 2025)
SKILL = {'QB': 'QB', 'RB': 'RB', 'FB': 'RB', 'WR': 'WR_TE', 'TE': 'WR_TE'}
PRACTICE = {'Did Not Participate In Practice': 'DID_NOT_PARTICIPATE', 'Limited Participation in Practice': 'LIMITED',
            'Full Participation in Practice': 'FULL'}
SOFT = ('hamstring', 'groin', 'calf', 'quad', 'thigh')
DESIG = {'Questionable': 'QUESTIONABLE', 'Doubtful': 'DOUBTFUL'}
EARLY_EXIT_FRAC = 0.75          # PREREG section 1
MIN_CELL = 30                   # PREREG section 2: a cell with n < 30 is shrunk toward its parent
PRIOR = 20                      # PREREG section 2: beta-binomial prior strength, pseudo-observations
SENSITIVITY_PRIORS = (5, 80)
B, SEED = 4000, 20261011        # PREREG section 4
GRID = [i / 100 for i in range(101)]


def _rows(path):
    with gzip.open(path, 'rt', encoding='utf-8', newline='') as fh:
        yield from csv.DictReader(fh)


def _one(prefix, season):
    hits = sorted(VINTAGE.glob(f'{prefix}_{season}.*.csv.gz'))
    if len(hits) != 1:
        raise SystemExit(f'{prefix}_{season}: expected exactly one stored file, found {len(hits)}')
    return hits[0]


def player_games(season):
    """{(week, club): {'game_id', 'n_team', 'on': {gsis: (n_on, last_index)}}} over scrimmage plays only."""
    games = collections.defaultdict(lambda: {'plays': [], 'on': collections.defaultdict(list)})
    for r in _rows(_one('hist_participation', season)):
        if not r['offense_formation'] or not r['offense_players']:
            continue                                       # special teams and unrecorded plays (PREREG: offensive plays)
        g = games[(r['nflverse_game_id'], r['possession_team'])]
        g['plays'].append(int(float(r['play_id'])))
        for p in r['offense_players'].split(';'):
            if p:
                g['on'][p].append(int(float(r['play_id'])))
    out = {}
    for (gid, club), g in games.items():
        parts = gid.split('_')
        week = int(parts[1])
        if week > 18:
            continue                                       # regular season only
        order = {pid: i for i, pid in enumerate(sorted(set(g['plays'])))}
        n_team = len(order)
        out[(week, club)] = {'game_id': gid, 'n_team': n_team,
                             'on': {p: (len(set(v)), max(order[x] for x in v) + 1) for p, v in g['on'].items()}}
    return out


def injury_rows(season):
    out = {}
    for r in _rows(_one('hist_injuries', season)):
        if r.get('game_type') != 'REG' or not r.get('gsis_id'):
            continue
        out[(int(r['week']), r['team'], r['gsis_id'])] = r
    return out


def build_units(seasons):
    """Designated skill player-games with outcomes, and the exclusions counted."""
    pg = {s: player_games(s) for s in sorted(set(seasons) | {min(seasons) - 1} if min(seasons) > 2016 else set(seasons))}
    inj = {s: injury_rows(s) for s in pg}
    # each player's game history: (season, week, club, r, designated)
    hist = collections.defaultdict(list)
    for s, games in pg.items():
        for (week, club), g in games.items():
            for p, (n_on, _last) in g['on'].items():
                d = (inj[s].get((week, club, p)) or {}).get('report_status') in ('Questionable', 'Doubtful', 'Out')
                hist[p].append((s, week, club, n_on / g['n_team'] if g['n_team'] else 0.0, d))
    for v in hist.values():
        v.sort()
    units, counts = [], collections.Counter()
    for s in seasons:
        for (week, club, p), r in inj[s].items():
            pos = SKILL.get(r.get('position'))
            if pos is None:
                continue
            rs = r.get('report_status') or ''
            pr = PRACTICE.get((r.get('practice_status') or '').strip(), 'NONE_RECORDED')
            if rs == 'Out':
                continue
            if rs in DESIG:
                desig = DESIG[rs]
            elif rs == '' and pr in ('LIMITED', 'DID_NOT_PARTICIPATE'):
                desig = 'NONE_WITH_LIMITED_OR_DNP_PRACTICE'
            else:
                continue
            g = pg[s].get((week, club))
            if g is None or not g['n_team']:
                counts['NO_CLUB_GAME_IN_PARTICIPATION'] += 1
                continue
            n_on, last = g['on'].get(p, (0, 0))
            inj_txt = f"{r.get('report_primary_injury') or ''} {r.get('practice_primary_injury') or ''}".lower()
            u = {'season': s, 'week': week, 'club': club, 'gsis': p, 'pos': pos, 'desig': desig, 'practice': pr,
                 'inj': 'SOFT_TISSUE_LOWER' if any(k in inj_txt for k in SOFT) else 'OTHER',
                 'played': n_on > 0, 'r': n_on / g['n_team'], 'cluster': f'{s}_{week}_{club}'}
            u['early_exit'] = bool(n_on > 0 and last / g['n_team'] < EARLY_EXIT_FRAC)
            # baseline r0: up to 4 most recent same-season, same-club undesignated games with >= 1 play
            prior = [h for h in hist.get(p, []) if (h[0], h[1]) < (s, week) and h[0] == s and h[2] == club
                     and not h[4] and h[3] > 0][-4:]
            if len(prior) < 2:
                prior = [h for h in hist.get(p, []) if h[0] == s - 1 and h[2] == club and not h[4] and h[3] > 0][-4:]
            if len(prior) >= 2:
                u['r0'] = statistics.median(h[3] for h in prior)
                u['r_rel'] = u['r'] / u['r0'] if u['r0'] > 0 else None
            else:
                u['r0'] = u['r_rel'] = None
                counts['NO_BASELINE'] += 1
            counts[f'units_{s}'] += 1
            units.append(u)
    return units, dict(counts)


LEVELS = (('desig', 'practice', 'pos', 'inj'), ('desig', 'practice', 'pos'), ('desig', 'pos'), ('desig',))


def _key(u, lv):
    return '|'.join(u[k] for k in lv)


def _quantiles(xs):
    xs = sorted(xs)
    if not xs:
        return None
    n = len(xs)
    return [round(xs[min(n - 1, int(q * (n - 1) + 0.5))], 5) for q in GRID]


def fit_table(units, prior=PRIOR):
    """Top-down: each level's estimate is shrunk toward its parent when n < MIN_CELL (PREREG section 2)."""
    stats = {lv: collections.defaultdict(lambda: {'n': 0, 'k': 0, 'r': [], 'played': 0, 'exit': 0}) for lv in LEVELS}
    for u in units:
        for lv in LEVELS:
            c = stats[lv][_key(u, lv)]
            c['n'] += 1
            c['k'] += 0 if u['played'] else 1
            if u['played']:
                c['played'] += 1
                c['exit'] += int(u['early_exit'])
                if u.get('r_rel') is not None:
                    c['r'].append(u['r_rel'])
    table = {}
    for depth in range(len(LEVELS) - 1, -1, -1):
        lv = LEVELS[depth]
        parent_lv = LEVELS[depth + 1] if depth + 1 < len(LEVELS) else None
        for key, c in stats[lv].items():
            par = table.get('|'.join(key.split('|')[:len(parent_lv)])) if parent_lv else None
            p_raw = c['k'] / c['n'] if c['n'] else None
            e_raw = c['exit'] / c['played'] if c['played'] else None
            shrink = par is not None and c['n'] < MIN_CELL
            p = ((c['k'] + prior * par['p_no_participation']) / (c['n'] + prior)) if shrink else p_raw
            e = (((c['exit'] + prior * par['p_early_exit']) / (c['played'] + prior)) if shrink and par['p_early_exit'] is not None
                 else e_raw)
            q = _quantiles(c['r'])
            if shrink and par.get('r_rel_quantiles'):
                w = len(c['r']) / (len(c['r']) + prior)
                q = ([round(w * a + (1 - w) * b, 5) for a, b in zip(q, par['r_rel_quantiles'])] if q
                     else par['r_rel_quantiles'])
            table[key] = {'level': '|'.join(lv), 'n': c['n'], 'n_played': c['played'], 'n_r': len(c['r']),
                          'p_no_participation': p, 'p_no_participation_raw': p_raw,
                          'p_early_exit': e, 'p_early_exit_raw': e_raw, 'r_rel_quantiles': q,
                          'shrunk_toward': ('|'.join(key.split('|')[:len(parent_lv)]) if shrink else None)}
    return table


def lookup(table, u):
    for lv in LEVELS:
        c = table.get(_key(u, lv))
        if c is not None and c['p_no_participation'] is not None:
            return c
    return None


_E2 = {}


def _crps_quantiles(q, x):
    """CRPS of an empirical distribution given by an equally spaced quantile grid, at x (Riemann on the grid)."""
    m = len(q)
    e1 = sum(abs(v - x) for v in q) / m
    k = tuple(q)
    if k not in _E2:
        _E2[k] = sum(abs(a - b) for a in q for b in q) / (m * m)
    return e1 - 0.5 * _E2[k]


def _logit(p):
    p = min(1 - 1e-6, max(1e-6, p))
    return math.log(p / (1 - p))


def _logistic_calibration(ps, ys):
    """(intercept, slope) of logit(P(y=1)) = a + b * logit(p), Newton-Raphson."""
    xs = [_logit(p) for p in ps]
    a, b = 0.0, 1.0

    def sig(z):                      # numerically stable; identical to 1/(1+e^-z) wherever that does not overflow
        if z >= 0:
            return 1 / (1 + math.exp(-z))
        e = math.exp(z)
        return e / (1 + e)
    for _ in range(50):
        ga = gb = haa = hab = hbb = 0.0
        for x, y in zip(xs, ys):
            m = sig(a + b * x)
            w = m * (1 - m)
            ga += y - m
            gb += (y - m) * x
            haa += w
            hab += w * x
            hbb += w * x * x
        det = haa * hbb - hab * hab
        if det <= 1e-12:
            break
        da, db = (hbb * ga - hab * gb) / det, (haa * gb - hab * ga) / det
        step = max(abs(da), abs(db))
        if step > 5:                 # damp a divergent Newton step (a near-separated bootstrap replicate)
            da, db = da * 5 / step, db * 5 / step
        a, b = a + da, b + db
        if abs(da) + abs(db) < 1e-9:
            break
    return a, b


def evaluate(table, units):
    rows = []
    for u in units:
        c = lookup(table, u)
        if c is None:
            continue
        y = 0 if u['played'] else 1
        row = {'cluster': u['cluster'], 'y': y, 'p': c['p_no_participation'],
               'brier_pm1': (c['p_no_participation'] - y) ** 2, 'brier_inc': float(y)}
        if u['played'] and u.get('r_rel') is not None and c.get('r_rel_quantiles'):
            row['crps_pm1'] = _crps_quantiles(c['r_rel_quantiles'], u['r_rel'])
            row['crps_inc'] = abs(u['r_rel'] - 1.0)
        rows.append(row)
    by = collections.defaultdict(list)
    for r in rows:
        by[r['cluster']].append(r)
    clusters = sorted(by)
    rng = random.Random(SEED)

    def stat(sample_rows):
        n = len(sample_rows)
        bi = sum(r['brier_inc'] - r['brier_pm1'] for r in sample_rows) / n
        cr = [r['crps_inc'] - r['crps_pm1'] for r in sample_rows if 'crps_pm1' in r]
        return bi, (sum(cr) / len(cr) if cr else None)

    base = stat(rows)
    a0, b0 = _logistic_calibration([r['p'] for r in rows], [r['y'] for r in rows])
    boots_b, boots_c, boots_a, boots_s = [], [], [], []
    for _ in range(B):
        samp = [r for c in (clusters[rng.randrange(len(clusters))] for _ in clusters) for r in by[c]]
        sb, sc = stat(samp)
        boots_b.append(sb)
        if sc is not None:
            boots_c.append(sc)
    rng2 = random.Random(SEED + 1)
    for _ in range(400):            # calibration refit is costlier; 400 replicates, declared here, reported
        samp = [r for c in (clusters[rng2.randrange(len(clusters))] for _ in clusters) for r in by[c]]
        a, b = _logistic_calibration([r['p'] for r in samp], [r['y'] for r in samp])
        boots_a.append(a)
        boots_s.append(b)

    def ci(xs):
        xs = sorted(xs)
        return [round(xs[int(0.025 * (len(xs) - 1))], 5), round(xs[int(0.975 * (len(xs) - 1))], 5)] if xs else None

    deciles = []
    srt = sorted(rows, key=lambda r: r['p'])
    for i in range(10):
        part = srt[i * len(srt) // 10:(i + 1) * len(srt) // 10]
        if part:
            deciles.append({'mean_p': round(sum(r['p'] for r in part) / len(part), 4),
                            'observed': round(sum(r['y'] for r in part) / len(part), 4), 'n': len(part)})
    out = {
        'n_units': len(rows), 'n_clusters': len(clusters), 'n_with_r': sum('crps_pm1' in r for r in rows),
        'base_rate_no_participation': round(sum(r['y'] for r in rows) / len(rows), 5),
        'H_a_brier_improvement': {'estimate': round(base[0], 6), 'ci95': ci(boots_b)},
        'H_b_calibration': {'intercept': round(a0, 4), 'intercept_ci95': ci(boots_a),
                            'slope': round(b0, 4), 'slope_ci95': ci(boots_s), 'deciles': deciles,
                            'bootstrap_replicates': len(boots_a)},
        'H_c_crps_improvement': {'estimate': round(base[1], 6) if base[1] is not None else None, 'ci95': ci(boots_c)},
    }
    ha = out['H_a_brier_improvement']['ci95']
    hc = out['H_c_crps_improvement']['ci95']
    hb = out['H_b_calibration']
    passes = {'H_a': bool(ha and ha[0] > 0), 'H_c': bool(hc and hc[0] > 0),
              'H_b': bool(hb['slope_ci95'] and hb['slope_ci95'][0] <= 1 <= hb['slope_ci95'][1]
                          and hb['intercept_ci95'] and hb['intercept_ci95'][0] <= 0 <= hb['intercept_ci95'][1])}
    reversed_ = bool((ha and ha[1] < 0) or (hc and hc[1] < 0))
    out['passes'] = passes
    out['verdict'] = ('NOT_EVALUABLE' if len(rows) < 500 else 'REVERSED' if reversed_
                      else 'SHADOW-CONTINUE' if all(passes.values()) else 'REJECT')
    return out


def main() -> int:
    units_fit, cnt_fit = build_units(FIT)
    table = fit_table(units_fit)
    sens = {str(p): {k: v['p_no_participation'] for k, v in fit_table(units_fit, prior=p).items()
                     if v['level'] == '|'.join(LEVELS[0])} for p in SENSITIVITY_PRIORS}
    (HERE / 'PM1_TABLE.json').write_text(json.dumps({
        'ARTIFACT': 'PM1_PARTICIPATION_TABLE', 'prereg': 'PREREG_PM1_PARTICIPATION.md (d3c0f775)',
        'fit_seasons': list(FIT), 'levels': ['|'.join(lv) for lv in LEVELS], 'min_cell': MIN_CELL, 'prior': PRIOR,
        'early_exit_frac': EARLY_EXIT_FRAC, 'r_rel_grid': GRID,
        'MEANING': ('p_no_participation: P(zero offensive plays | designated, not ruled out). r_rel_quantiles: the '
                    'distribution of offensive-play share relative to the player\'s own baseline, among those who played. '
                    'p_early_exit: P(last on-field play before 75% of the club\'s plays | played).'),
        'cells': table, 'sensitivity_prior_p_no_participation': sens}, indent=1) + '\n')
    frozen = json.loads((HERE / 'PM1_TABLE.json').read_text())['cells']       # evaluate the FROZEN table
    units_held, cnt_held = build_units(HELD)
    ev = evaluate(frozen, units_held)
    (HERE / 'PM1_EVALUATION.json').write_text(json.dumps({'ARTIFACT': 'PM1_EVALUATION', 'held_out_seasons': list(HELD),
                                                          'bootstrap': {'B': B, 'seed': SEED, 'cluster': 'club-week'},
                                                          **ev}, indent=1) + '\n')
    (HERE / 'PM1_UNITS_SUMMARY.json').write_text(json.dumps({'fit': cnt_fit, 'held_out': cnt_held,
                                                             'n_fit_units': len(units_fit),
                                                             'n_held_units': len(units_held)}, indent=1) + '\n')
    print(json.dumps({k: ev[k] for k in ('n_units', 'n_clusters', 'n_with_r', 'base_rate_no_participation',
                                         'H_a_brier_improvement', 'H_c_crps_improvement', 'passes', 'verdict')}))
    print('H_b', {k: ev['H_b_calibration'][k] for k in ('intercept', 'intercept_ci95', 'slope', 'slope_ci95')})
    return 0


if __name__ == '__main__':
    sys.exit(main())
