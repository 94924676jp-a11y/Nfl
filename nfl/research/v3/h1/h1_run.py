"""H1 step 3: forecast every eligible 2025 starting-QB game, forward-chained.

THE MECHANISM IS IMPORTED, NOT REIMPLEMENTED. `qb2_lib.attach`, `.pools`,
`.simulate`, `._mix`, `.rung_weight` and `.rung_rate` are called unmodified.
`p4b_volume.attach`, `.baselines`, `.build_forms` and `.draw` are called
unmodified -- the same four `nfl/production/team_volume_v1.py` imports. The
only thing written here is the plumbing that drives them over 2025 and the
scoring that reads their output.

THE V AND S LAYERS. `simulate` returns draw matrices but not the team-dropback
level V or the quarterback share S it built them from. They are reproduced
here by seeding `numpy.random.default_rng` exactly as `simulate` does and
calling `qb2_lib._mix` in the same order, and the reproduction is CHECKED:
`rint(V*S)` must equal `simulate`'s own `db` matrix cell for cell. If it does
not, the run raises rather than scoring a layer it cannot prove it observed.

EXPLORATORY. 2025 is development data in this project.
"""
from __future__ import annotations

import collections
import csv
import gzip
import json
import math
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[4]
for _q in (str(_REPO), str(_REPO / 'nfl' / 'research' / 'qb2'),
           str(_REPO / 'nfl' / 'research' / 'rc1'),
           str(_REPO / 'nfl' / 'research' / 'p4b'),
           str(_REPO / 'nfl' / 'research' / 'v3' / 'h1')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

import qb2_lib as Q                                               # noqa: E402
import p4b_volume as PV                                           # noqa: E402
import h1_frame as FR                                             # noqa: E402

HERE = _REPO / 'nfl' / 'research' / 'v3' / 'h1'
ROWS_OUT = HERE / 'H1_RESIDUALS.csv.gz'
DRAWS_OUT = HERE / 'h1_pyds_draws.npy'
META_OUT = HERE / 'h1_run_meta.json'

EVAL_SEASON = 2025
RUNG = 'L1'                 # the production baseline selection, qb_v1
SEED = 20260908             # qb_v1.forecast default
M = 1000
MIN_DB = 10                 # predeclared, H1_PREREGISTRATION section 1
PIT_SEED = 20260915


# --------------------------------------------------------------- eligibility
def eligible(rows, season=EVAL_SEASON, min_db=MIN_DB):
    """Predeclared in H1_PREREGISTRATION section 1. Counted at every clause."""
    tally = collections.Counter()
    keep, primary_no_hist, dropped_lowdb = [], [], []
    team_first = {}
    for r in sorted(rows, key=lambda x: x['ord']):
        team_first.setdefault(r['team'], r['ord'])
    for r in rows:
        if r['season'] != season:
            continue
        tally['season_rows'] += 1
        if r['qb_ord'] != 1:
            tally['not_primary_passer'] += 1
            continue
        tally['primary_passer'] += 1
        if r['h_games'] < 1:
            tally['no_prior_appearance'] += 1
            primary_no_hist.append((r['game_id'], r['team'], r['gsis_id']))
            continue
        tally['has_prior_appearance'] += 1
        if not r['h_team_db_series']:
            tally['team_has_no_prior_game'] += 1
            continue
        tally['team_has_prior_game'] += 1
        if r['db'] < min_db:
            tally['below_min_dropbacks'] += 1
            dropped_lowdb.append((r['game_id'], r['team'], r['gsis_id'],
                                  r['db']))
            r['_frame'] = 'UNFILTERED_ONLY'
            keep.append(r)
            continue
        tally['eligible'] += 1
        r['_frame'] = 'PRIMARY'
        keep.append(r)
    if not keep:
        raise SystemExit('H1_ELIGIBLE_EMPTY: no rows survived eligibility. '
                         'An empty frame is an error, not a result.')
    return keep, {'tally': dict(tally),
                  'primary_passers_without_prior_appearance': primary_no_hist,
                  'dropped_below_min_dropbacks': dropped_lowdb,
                  'min_dropbacks': min_db}


# -------------------------------------------------------- the V / S recovery
def vs_draws(r, po, rung=RUNG, seed=SEED, m=M):
    """Reproduce simulate's V and S with its own RNG stream and its own _mix."""
    rng = np.random.default_rng(
        [seed, int(r['ord']),
         int.from_bytes(str(r['gsis_id']).encode()[-8:], 'little')])
    w = Q.rung_weight(r, rung)
    ew = rung in ('L2', 'L3')
    V = Q._mix(rng, r['h_team_db_series'], po['team_db'], w, m, ew)
    S = np.clip(Q._mix(rng, r['h_share'], po['share'], w, m, ew), 0, 1)
    return V, S


def point_rates(r, po, rung=RUNG):
    """The rung rates simulate uses. Point values, read from the same code."""
    pa = Q.rung_rate(r, 'att', 'db', rung, po['p_att'])
    ps = Q.rung_rate(r, 'sacks', 'db', rung, po['p_sack'])
    psc = Q.rung_rate(r, 'scr', 'db', rung, po['p_scr'])
    tot = max(pa + ps + psc, 1e-9)
    pc = Q.rung_rate(r, 'cmp', 'att', rung, po['p_cmp'])
    ptd = Q.rung_rate(r, 'ptd', 'cmp', rung, po['p_ptd'])
    pint = Q.rung_rate(r, 'int', 'att', rung, po['p_int'], den_offset='cmp')
    dpd = Q.rung_rate(r, 'drush', 'db', rung, po['drush_per_db'])
    return {'p_att': pa / tot, 'p_sack': ps / tot, 'p_scr': psc / tot,
            'p_cmp': pc, 'p_ptd_per_cmp': ptd, 'p_int_per_inc': pint,
            'p_drush_per_db': dpd, 'own_weight': Q.rung_weight(r, rung)}


# ------------------------------------------------------------ P4B team layer
def p4b_layer(key, eval_season=EVAL_SEASON):
    """P4B's outer and inner passes for one denominator, one season.

    Transcribed from `p4b_volume.main`'s loop body and restricted to a single
    evaluation season. Every mathematical step is the imported function.
    """
    with gzip.open(_REPO / 'nfl' / 'research' / 'inputs' /
                   'denom_panel.csv.gz', 'rt', newline='') as fh:
        raw = list(csv.DictReader(fh))
    if not raw:
        raise SystemExit('H1_DENOM_PANEL_EMPTY')
    rows = []
    for r in raw:
        d = dict(r)
        for k in ('season', 'week', 'ord'):
            d[k] = int(d[k])
        for k in PV.DEN:
            d[k] = int(d[k])
        rows.append(d)
    rows.sort(key=lambda x: (x['ord'], x['team']))
    rows = PV.attach(rows, key)
    rows = [r for r in rows if r[key] > 0]

    inner = eval_season - 1
    tr_i = [r for r in rows if r['season'] < inner]
    va_i = [r for r in rows if r['season'] == inner]
    if len(tr_i) < 200 or len(va_i) < 100:
        raise SystemExit(f'H1_P4B_INNER_TOO_SMALL: {key}')
    lm_i = float(np.mean([r[key] for r in tr_i]))
    for r in rows:
        r['_b'] = PV.baselines(r, lm_i)
    est_i = min(PV.BASELINES,
                key=lambda b: np.mean([abs(r[key] - r['_b'][b]) for r in tr_i]))
    for r in tr_i + va_i:
        r['_resid'] = r[key] - r['_b'][est_i]
    fit_i = PV.build_forms(tr_i, key, PV.SEED)
    yv = np.array([r[key] for r in va_i], float)
    pv = np.array([r['_b'][est_i] for r in va_i], float)
    inner_crps = {}
    for f in PV.FORMS:
        rng = np.random.default_rng(PV.SEED + 7)
        dd = pv.reshape(-1, 1) + PV.draw(f, fit_i, va_i, rng)
        inner_crps[f] = float(PV.crps_samples(dd, yv).mean())
    uncond = [f for f in PV.FORMS
              if f in ('empirical', 'gaussian', 'student_t')]
    b_form = min(uncond, key=lambda f: inner_crps[f])

    tr = [r for r in rows if r['season'] < eval_season]
    te = [r for r in rows if r['season'] == eval_season]
    if not te:
        raise SystemExit(f'H1_P4B_EMPTY_EVAL: {key}')
    lm = float(np.mean([r[key] for r in tr]))
    for r in rows:
        r['_b'] = PV.baselines(r, lm)
    est = min(PV.BASELINES,
              key=lambda b: np.mean([abs(r[key] - r['_b'][b]) for r in tr]))
    for r in tr + te:
        r['_resid'] = r[key] - r['_b'][est]
    fit = PV.build_forms(tr, key, PV.SEED)
    p = np.array([r['_b'][est] for r in te], float)
    rngB = np.random.default_rng(PV.SEED + 101)
    d = p.reshape(-1, 1) + PV.draw(b_form, fit, te, rngB)
    n_neg = int((d < 0).sum())
    np.clip(d, 0, None, out=d)
    idx = {(r['team'], r['ord']): i for i, r in enumerate(te)}
    return {'key': key, 'point_estimator': est, 'form': b_form,
            'inner_validation_season': inner, 'inner_crps': inner_crps,
            'n_eval': len(te), 'n_train': len(tr),
            'train_seasons': sorted({r['season'] for r in tr}),
            'negative_draw_rate': n_neg / d.size,
            'draws': d, 'index': idx,
            'realized': {(r['team'], r['ord']): r[key] for r in te}}


# ---------------------------------------------------------------- scoring
def rpit(draws, y, rng):
    """Randomized PIT. Required for the discrete counts."""
    d = np.asarray(draws, float)
    lo = float((d < y).mean())
    hi = float((d <= y).mean())
    return lo + float(rng.random()) * (hi - lo)


def cpit(draws, y):
    d = np.asarray(draws, float)
    return float((d < y).mean() + 0.5 * (d == y).mean())


def score(draws, y, rng, discrete):
    d = np.asarray(draws, float)
    mu = float(d.mean())
    sd = float(d.std(ddof=1)) if len(d) > 1 else 0.0
    q = np.percentile(d, [10, 50, 90])
    return {
        'pred_mean': mu, 'pred_sd': sd,
        'pred_p10': float(q[0]), 'pred_p50': float(q[1]),
        'pred_p90': float(q[2]),
        'actual': float(y),
        'error': mu - float(y),
        'z': (mu - float(y)) / sd if sd > 0 else float('nan'),
        'crps': float(PV.crps_samples(d.reshape(1, -1),
                                      np.array([float(y)]))[0]),
        'pit': rpit(d, y, rng) if discrete else cpit(d, y),
        'pit_kind': 'RANDOMIZED' if discrete else 'CONTINUOUS',
        'below_p10': int(y < q[0]), 'below_p50': int(y < q[1]),
        'below_p90': int(y < q[2]),
        'in_p10_p90': int(q[0] <= y <= q[2]),
    }


def ratio_draws(num, den):
    """A genuine predictive distribution for a ratio, draw by draw."""
    n = np.asarray(num, float)
    d = np.asarray(den, float)
    ok = d > 0
    if not ok.any():
        return None
    return n[ok] / d[ok]


# ---------------------------------------------------------------- the run
def run():
    rows, fmeta = FR.build()
    Q.attach(rows)
    allrows = rows
    keep, emeta = eligible(rows)
    primary = [r for r in keep if r['_frame'] == 'PRIMARY']
    if not primary:
        raise SystemExit('H1_PRIMARY_FRAME_EMPTY')

    po = Q.pools(allrows, EVAL_SEASON)
    D = Q.simulate(keep, EVAL_SEASON, allrows, seed=SEED, m=M, rung=RUNG)
    for f in ('db', 'att', 'cmp', 'pyds', 'ptd', 'int', 'sacks', 'scr',
              'rush_opp'):
        if f not in D or D[f].shape != (len(keep), M):
            raise SystemExit(f'H1_SIMULATE_SHAPE: {f}')

    plays = p4b_layer('team_off_snaps')
    tdb = p4b_layer('team_dropbacks_part')

    rng = np.random.default_rng(PIT_SEED)
    out = []
    pyds_draws = np.zeros((len(keep), M), np.float32)
    vs_mismatch = 0
    for i, r in enumerate(keep):
        V, S = vs_draws(r, po)
        DBchk = np.maximum(np.rint(V * S), 0).astype(int)
        if not np.array_equal(DBchk, D['db'][i].astype(int)):
            vs_mismatch += 1
        pr = point_rates(r, po)
        pyds_draws[i] = D['pyds'][i]
        tk = (r['team'], r['ord'])

        layers = []
        if tk in plays['index']:
            layers.append(('team_offensive_plays',
                           plays['draws'][plays['index'][tk]],
                           plays['realized'][tk], True))
        if tk in tdb['index']:
            layers.append(('team_dropbacks_p4b',
                           tdb['draws'][tdb['index'][tk]],
                           tdb['realized'][tk], True))
        layers.append(('team_dropbacks_qb2', V, r['team_db'], False))
        layers.append(('qb_dropback_share', S,
                       r['db'] / r['team_db'] if r['team_db'] else float('nan'),
                       False))
        layers.append(('qb_dropbacks', D['db'][i], r['db'], True))
        layers.append(('qb_attempts', D['att'][i], r['att'], True))
        layers.append(('qb_completions', D['cmp'][i], r['cmp'], True))
        layers.append(('qb_sacks', D['sacks'][i], r['sacks'], True))
        layers.append(('qb_scrambles', D['scr'][i], r['scr'], True))
        layers.append(('qb_rush_opportunities', D['rush_opp'][i],
                       r['rush_opp'], True))
        layers.append(('qb_pass_td', D['ptd'][i], r['ptd'], True))
        layers.append(('qb_interceptions', D['int'][i], r['int'], True))
        layers.append(('qb_passing_yards', D['pyds'][i], r['pyds'], False))

        # ratio layers, as predictive distributions over draws
        rl = [
            ('att_per_dropback', ratio_draws(D['att'][i], D['db'][i]),
             r['att'] / r['db'] if r['db'] else None),
            ('cmp_per_attempt', ratio_draws(D['cmp'][i], D['att'][i]),
             r['cmp'] / r['att'] if r['att'] else None),
            ('yards_per_completion', ratio_draws(D['pyds'][i], D['cmp'][i]),
             r['pyds'] / r['cmp'] if r['cmp'] else None),
            ('ptd_per_attempt', ratio_draws(D['ptd'][i], D['att'][i]),
             r['ptd'] / r['att'] if r['att'] else None),
            ('ptd_per_completion', ratio_draws(D['ptd'][i], D['cmp'][i]),
             r['ptd'] / r['cmp'] if r['cmp'] else None),
            ('int_per_attempt', ratio_draws(D['int'][i], D['att'][i]),
             r['int'] / r['att'] if r['att'] else None),
            ('scr_per_rush_opportunity',
             ratio_draws(D['scr'][i], D['rush_opp'][i]),
             r['scr'] / r['rush_opp'] if r['rush_opp'] else None),
        ]
        for nm, dd, y in rl:
            if dd is None or y is None or len(dd) < 2:
                continue
            layers.append((nm, dd, y, False))

        base = {'season': r['season'], 'week': r['week'],
                'game_id': r['game_id'], 'team': r['team'],
                'opponent': r['opponent'], 'home': r['home'],
                'gsis_id': r['gsis_id'], 'frame': r['_frame'],
                'h_games': r['h_games'], 'own_weight': round(pr['own_weight'], 6),
                'realised_db': r['db'], 'realised_att': r['att'],
                'realised_cmp': r['cmp'], 'realised_pyds': r['pyds'],
                'team_db': r['team_db'], 'team_plays': r['team_plays'],
                'n_qb_in_team_game': r['n_qb_in_team_game']}
        for nm, dd, y, disc in layers:
            if y is None or (isinstance(y, float) and math.isnan(y)):
                continue
            s = score(dd, y, rng, disc)
            rec = dict(base)
            rec['layer'] = nm
            rec.update({k: (round(v, 8) if isinstance(v, float) else v)
                        for k, v in s.items()})
            out.append(rec)

    if not out:
        raise SystemExit('H1_NO_SCORED_ROWS: empty is an error, not a result.')
    if vs_mismatch:
        raise SystemExit(
            f'H1_VS_REPRODUCTION_FAILED: {vs_mismatch} of {len(keep)} rows '
            f'could not be reproduced from simulate\'s own RNG stream. The V '
            f'and S layers are not scored on a stream this task cannot prove '
            f'it observed.')

    with gzip.open(ROWS_OUT, 'wt', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    np.save(DRAWS_OUT, pyds_draws)

    meta = {
        'artifact': 'NFL_H1_RUN_META',
        'spec_version': 'h1-run-1',
        'status': 'EXPLORATORY -- 2025 is development data in this project',
        'eval_season': EVAL_SEASON, 'rung': RUNG, 'seed': SEED,
        'n_draws': M, 'pit_seed': PIT_SEED,
        'frame': fmeta, 'eligibility': emeta,
        'n_rows_simulated': len(keep),
        'n_primary_frame': len(primary),
        'n_scored_rows': len(out),
        'n_layers': len(sorted({r['layer'] for r in out})),
        'layers': sorted({r['layer'] for r in out}),
        'vs_reproduction_exact': True,
        'p4b_team_off_snaps': {k: v for k, v in plays.items()
                               if k not in ('draws', 'index', 'realized')},
        'p4b_team_dropbacks_part': {k: v for k, v in tdb.items()
                                    if k not in ('draws', 'index',
                                                 'realized')},
        'q7_crosscheck': FR.q7_crosscheck(rows),
    }
    META_OUT.write_text(json.dumps(meta, indent=1, default=str) + '\n')
    return meta


if __name__ == '__main__':
    m = run()
    print(json.dumps({k: v for k, v in m.items()
                      if k not in ('eligibility', 'frame')}, indent=1,
                     default=str)[:3000])
    print('eligibility tally:', json.dumps(m['eligibility']['tally'], indent=1))
