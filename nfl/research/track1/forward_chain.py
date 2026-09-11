"""Track 1 step 4: forward-chained BASELINE vs TRACK1, one change only.

    python3.12 -m nfl.research.track1.forward_chain

THE TWO ARMS, AND THE ONE DIFFERENCE BETWEEN THEM.

  BASELINE  point = the frozen P4B estimator for that season, fitted on every
            team-game strictly earlier than the week being forecast;
            predictive draws = point + a residual resampled from that same
            strictly-earlier history.

  TRACK1    point = the SAME baseline point, multiplied by a simulated
            game-state response normalised to mean 1.0 over the training
            frame; predictive draws = that per-draw point + a residual
            resampled from the residuals of the SAME construction on the
            training frame.

Everything else is held fixed and shared: the point estimator, the residual
form, the training window, the draw count, and -- deliberately -- the residual
INDICES, so the two arms differ by the multiplier and not by which residuals
they happened to draw. Common random numbers make a paired comparison of two
noisy quantities measure the treatment instead of the noise.

THE TREATMENT CANNOT WIN BY SHIFTING THE LEVEL. The multiplier is divided by
its own training-frame mean, so Track 1 has exactly the baseline's average
level and differs only in how it distributes that level across games.

THE TREATMENT IS NOT PROTECTED FROM ITS OWN WIDTH. Per-draw state adds
variance. If the state does not actually explain variance, the Track 1
predictive distribution is wider than the baseline's for no reason and CRPS
punishes it. Nothing here rescales that away.

WHY A THIRD, DIAGNOSTIC ARM. TRACK1_MEAN uses the EXPECTED multiplier rather
than a per-draw one. Comparing it to both arms separates "the conditional mean
moved in the right direction" (discrimination) from "the predictive width
changed". They are different properties and a single CRPS number hides which
one moved.

WHAT IS NOT CLAIMED. The downstream quarterback numbers come from a
PROPAGATION HARNESS, not from the production QB layer: a fixed, forward-chained
room-share and efficiency model that is byte-identical across arms, so a
difference in QB CRPS is attributable to the team budget and to nothing else.
It measures propagation of a volume change. It does not measure the production
quarterback model, and it is never reported as though it did.
"""
from __future__ import annotations

import argparse
import collections
import csv
import gzip
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
for _q in (str(_REPO), str(_REPO / 'nfl' / 'research' / 'p4b')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

import p4b_volume as V                                           # noqa: E402
from nfl.research.track1 import response as RESP                 # noqa: E402
from nfl.research.track1 import state as ST                      # noqa: E402

SPEC_VERSION = 'track1-forward-chain-1'
HERE = _REPO / 'nfl' / 'research' / 'track1'
DENOM = _REPO / 'nfl' / 'research' / 'inputs' / 'denom_panel.csv.gz'
RESULTS = _REPO / 'nfl' / 'research' / 'p4b' / 'volume_results.json'

METRICS = ('team_off_snaps', 'team_dropbacks_part', 'team_targets',
           'team_carries', 'team_rz_carries')
EVAL_SEASONS = (2022, 2023, 2024, 2025)
N_DRAWS = 1000
SEED = 20260911
MU_GRID = np.arange(-28.0, 28.0001, 0.1)

ARMS = ('BASELINE', 'TRACK1', 'TRACK1_MEAN')


def estimator_for(metric, season):
    """The frozen P4B point estimator selected FOR this season.

    Read from the frozen research output, never re-chosen here. Both arms use
    the same one, so any property of that selection is common to both and
    cancels out of the comparison.
    """
    res = json.loads(RESULTS.read_text())[metric]
    if str(season) in res:
        return res[str(season)]['point_estimator'], int(season)
    ev = max(int(k) for k in res if int(k) < season)
    return res[str(ev)]['point_estimator'], ev


def load_denom():
    rows = []
    with gzip.open(DENOM, 'rt', newline='') as fh:
        for r in csv.DictReader(fh):
            for k in ('season', 'week', 'ord'):
                r[k] = int(r[k])
            for k in METRICS:
                r[k] = int(r[k])
            r['home'] = int(r['home']) if str(r['home']).strip() else 0
            rows.append(r)
    rows.sort(key=lambda x: (x['ord'], x['team']))
    return rows


def _mu_table(state_fit, response_fit, grid=MU_GRID):
    """E[multiplier | expected margin], exactly, for both sides of a game.

    Exact rather than sampled: under the resampling generator the state
    distribution IS the empirical distribution over training increment
    residuals, so enumerating them gives the expectation with no Monte Carlo
    error in the training-frame normalisation.
    """
    R = state_fit['increment_residuals']
    lam = np.asarray(state_fit['drift_share_by_quarter'], float)
    n = R.shape[0]
    G = len(grid)
    mu = np.repeat(np.asarray(grid, float), n)
    e = np.tile(R, (G, 1))
    s2 = lam[0] * mu + e[:, 0]
    s3 = s2 + lam[1] * mu + e[:, 1]
    s4 = s3 + lam[2] * mu + e[:, 2]
    B = np.empty((G * n, 4), int)
    B[:, 0] = RESP.NEUTRAL
    B[:, 1] = RESP.bucket_index(s2)
    B[:, 2] = RESP.bucket_index(s3)
    B[:, 3] = RESP.bucket_index(s4)
    out = {}
    for side, BB in (('home', B), ('away', ST.mirror(B))):
        m = RESP.multipliers(BB, response_fit)
        out[side] = {k: v.reshape(G, n).mean(axis=1) for k, v in m.items()}
    return {'grid': np.asarray(grid, float), 'by_side': out}


def _mu_lookup(table, side, driver, mu):
    return np.interp(np.asarray(mu, float), table['grid'],
                     table['by_side'][side][driver])


def _crps(draws, y):
    return V.crps_samples(draws, np.asarray(y, float))


def _pit(draws, y):
    below = (draws < y.reshape(-1, 1)).mean(axis=1)
    at = (draws == y.reshape(-1, 1)).mean(axis=1)
    return below + 0.5 * at


def _coverage(draws, y, levels=(0.50, 0.80, 0.90, 0.95)):
    out = {}
    for L in levels:
        lo = np.percentile(draws, 100 * (1 - L) / 2, axis=1)
        hi = np.percentile(draws, 100 - 100 * (1 - L) / 2, axis=1)
        out[f'{int(L * 100)}'] = float(((y >= lo) & (y <= hi)).mean())
    return out


# --------------------------------------------------------------- the chain
def run(eval_seasons=EVAL_SEASONS, n_draws=N_DRAWS, seed=SEED,
        out_dir=None, progress=False):
    out_dir = pathlib.Path(out_dir or HERE)
    den = load_denom()
    panels = RESP.load_panels()
    games = panels['game']
    tq = panels['team_quarter']
    qb = panels['qb_game']

    by_key = {}
    for g in games:
        by_key[(g['season'], g['week'], g['home_team'])] = (g, 'home')
        by_key[(g['season'], g['week'], g['away_team'])] = (g, 'away')

    # room totals per team-game, from the same play stream as the budget
    room = collections.defaultdict(collections.Counter)
    for q in qb:
        c = room[(q['season'], q['week'], q['team'])]
        c['dropbacks'] += q['dropbacks']
        c['attempts'] += q['attempts']
        c['pass_yards'] += q['pass_yards']

    # ATTACH ONCE PER METRIC over the whole panel. `attach` gives every row its
    # STRICTLY EARLIER history by construction, so re-running it per week would
    # produce identical values at much greater cost.
    attached = {}
    for m in METRICS:
        rows = [dict(r) for r in den]
        V.attach(rows, m)
        attached[m] = rows

    rows_out = []
    diag_rows = []
    half_life_by_season = {}
    fitted_log = []

    for Y in eval_seasons:
        prior_games = [g for g in games if g['season'] < Y]
        hl = ST.select_half_life(prior_games)
        half_life_by_season[Y] = hl
        weeks = sorted({r['week'] for r in den if r['season'] == Y})
        for w in weeks:
            cut = Y * 100 + w
            tr_tq = [r for r in tq if (r['season'] * 100 + r['week']) < cut]
            tr_gm = [g for g in games if (g['season'] * 100 + g['week']) < cut]
            ev_idx = [i for i, r in enumerate(den) if r['ord'] == cut]
            if not ev_idx or not tr_tq or len(tr_gm) < 50:
                continue
            rfit = RESP.fit_response(tr_tq)
            sfit = ST.fit_state(tr_gm)
            sfit['half_life'] = hl['half_life']
            table = _mu_table(sfit, rfit)

            # expected margin for every game up to and including this week
            upto = [g for g in games
                    if (g['season'] * 100 + g['week']) <= cut]
            ss = {s['game_id']: s for s in
                  ST.strength_series(upto, hl['half_life'])}
            mu_of = {}
            for g in upto:
                s = ss[g['game_id']]
                mu_of[g['game_id']] = ST.expected_margin(sfit,
                                                         s['strength_diff'])

            rng = np.random.default_rng([seed, Y, w])
            tr_idx = [i for i, r in enumerate(den) if r['ord'] < cut]

            for metric in METRICS:
                est, est_season = estimator_for(metric, Y)
                rows = attached[metric]
                lm = float(np.mean([rows[i][metric] for i in tr_idx
                                    if rows[i][metric] > 0]))
                b_tr = np.array([V.baselines(rows[i], lm)[est]
                                 for i in tr_idx], float)
                y_tr = np.array([rows[i][metric] for i in tr_idx], float)
                driver = RESP.METRIC_DRIVER.get(metric)

                if driver:
                    mh_tr = np.array([_side_mu(by_key, mu_of, rows[i], table,
                                               driver) for i in tr_idx], float)
                    mbar = float(mh_tr.mean())
                    if not np.isfinite(mbar) or mbar <= 0:
                        mbar = 1.0
                    p_tr_t1 = b_tr * mh_tr / mbar
                else:
                    mh_tr = np.ones(len(tr_idx))
                    mbar = 1.0
                    p_tr_t1 = b_tr

                res_base = y_tr - b_tr
                res_t1 = y_tr - p_tr_t1
                keep = np.isfinite(res_base) & np.isfinite(res_t1) & (y_tr > 0)
                res_base, res_t1 = res_base[keep], res_t1[keep]
                if len(res_base) < 100:
                    continue

                for i in ev_idx:
                    r = rows[i]
                    y = float(r[metric])
                    if y <= 0:
                        continue
                    b = float(V.baselines(r, lm)[est])
                    gsd = by_key.get((r['season'], r['week'], r['team']))
                    if gsd is None:
                        continue
                    g, side = gsd
                    mu = mu_of[g['game_id']]
                    # COMMON RANDOM NUMBERS: one index array, both arms.
                    ridx = rng.integers(0, len(res_base), size=n_draws)
                    B, _ = ST.simulate_buckets(sfit, mu, n_draws, rng)
                    if side == 'away':
                        B = ST.mirror(B)
                    if driver:
                        m_draw = RESP.multipliers(B, rfit)[driver] / mbar
                        m_hat = float(_side_mu(by_key, mu_of, r, table,
                                               driver) / mbar)
                    else:
                        m_draw = np.ones(n_draws)
                        m_hat = 1.0
                    d = {
                        'BASELINE': b + res_base[ridx],
                        'TRACK1': b * m_draw + res_t1[ridx],
                        'TRACK1_MEAN': b * m_hat + res_t1[ridx],
                    }
                    rec = {'season': r['season'], 'week': r['week'],
                           'team': r['team'], 'opponent': r['opponent'],
                           'game_id': g['game_id'], 'side': side,
                           'metric': metric, 'actual': y,
                           'estimator': est, 'estimator_season': est_season,
                           'expected_margin': round(float(mu), 4),
                           'multiplier_expected': round(m_hat, 6),
                           'baseline_point': round(b, 4)}
                    for arm in ARMS:
                        dr = d[arm]
                        rec[f'{arm}_crps'] = float(_crps(
                            dr.reshape(1, -1), np.array([y]))[0])
                        rec[f'{arm}_mean'] = float(dr.mean())
                        rec[f'{arm}_pit'] = float(_pit(
                            dr.reshape(1, -1), np.array([y]))[0])
                        rec[f'{arm}_sd'] = float(dr.std(ddof=1))
                        for L, lo, hi in _levels(dr):
                            rec[f'{arm}_cov{L}'] = int(lo <= y <= hi)
                    rows_out.append(rec)

                    if metric == 'team_dropbacks_part':
                        diag_rows.extend(_qb_propagation(
                            r, g, side, room, qb, den, tr_idx, attached,
                            d, y, rng, n_draws))
            fitted_log.append({'season': Y, 'week': w,
                               'n_train_team_quarters': len(tr_tq),
                               'n_train_games': len(tr_gm),
                               'half_life': hl['half_life'],
                               'home_field_advantage': round(
                                   sfit['home_field_advantage'], 4),
                               'strength_slope': round(
                                   sfit['strength_slope'], 4)})
            if progress:
                print(f'  {Y} w{w:02d}  rows={len(rows_out)}', flush=True)
    return {'rows': rows_out, 'diagnostics': diag_rows,
            'half_life_by_season': half_life_by_season,
            'fit_log': fitted_log}


def _levels(draws, levels=(50, 80, 90, 95)):
    for L in levels:
        lo = float(np.percentile(draws, (100 - L) / 2))
        hi = float(np.percentile(draws, 100 - (100 - L) / 2))
        yield L, lo, hi


def _side_mu(by_key, mu_of, row, table, driver):
    gsd = by_key.get((row['season'], row['week'], row['team']))
    if gsd is None:
        return 1.0
    g, side = gsd
    return float(_mu_lookup(table, side, driver, mu_of[g['game_id']]))


# ------------------------------------------- downstream propagation harness
def _qb_propagation(row, game, side, room, qb_rows, den, tr_idx, attached,
                    budget_draws, y_budget, rng, n_draws):
    """Propagate the team dropback budget to the QB ROOM. Fixed across arms.

    THE ROOM, NOT THE INDIVIDUAL. NE@SEA is why: Seattle's room aggregate was
    nearly exact while the split inside it was maximally wrong, because the
    starter was injured early. No pregame information set can observe that, and
    charging it to a volume experiment would be measuring the wrong thing.

    THE CONVERSION MODEL IS IDENTICAL IN BOTH ARMS -- the same league ratio,
    the same efficiency pool, the same random indices. Any difference in the
    final passing-yard distribution is therefore caused by the budget and by
    nothing else, which is exactly what the volume-versus-efficiency
    decomposition needs.
    """
    key = (row['season'], row['week'], row['team'])
    got = room.get(key)
    if not got:
        return []
    hist = [(r['season'], r['week'], r['team']) for r in den
            if (r['season'] * 100 + r['week']) < row['season'] * 100 + row['week']]
    conv, ypa, ratio = [], [], []
    for k in hist:
        c = room.get(k)
        if not c or not c['dropbacks'] or not c['attempts']:
            continue
        conv.append(c['attempts'] / c['dropbacks'])
        ypa.append(c['pass_yards'] / c['attempts'])
    if len(conv) < 200:
        return []
    conv = np.asarray(conv, float)
    ypa = np.asarray(ypa, float)
    # the budget metric is team_dropbacks_part; the room's own dropback count
    # is a different measurement of the same thing, so the ratio is fitted
    # rather than assumed to be one.
    den_by_key = {(r['season'], r['week'], r['team']): r for r in den}
    rr = [room[k]['dropbacks'] / den_by_key[k]['team_dropbacks_part']
          for k in hist
          if k in room and den_by_key.get(k, {}).get('team_dropbacks_part')]
    ratio = float(np.mean(rr)) if rr else 1.0

    ci = rng.integers(0, len(conv), size=n_draws)
    yi = rng.integers(0, len(ypa), size=n_draws)
    out = []
    a_db, a_att = float(got['dropbacks']), float(got['attempts'])
    a_yds = float(got['pass_yards'])
    for arm, bud in budget_draws.items():
        db = np.clip(bud, 0, None) * ratio
        att = db * conv[ci]
        yds = att * ypa[yi]
        out.append({
            'season': row['season'], 'week': row['week'], 'team': row['team'],
            'game_id': game['game_id'], 'side': side, 'arm': arm,
            'actual_room_dropbacks': a_db, 'actual_room_attempts': a_att,
            'actual_room_pass_yards': a_yds,
            'actual_ypa': round(a_yds / a_att, 5) if a_att else '',
            'pred_room_dropbacks': round(float(db.mean()), 4),
            'pred_room_attempts': round(float(att.mean()), 4),
            'pred_room_pass_yards': round(float(yds.mean()), 4),
            'pred_ypa': round(float(ypa[yi].mean()), 5),
            'crps_room_dropbacks': round(float(_crps(
                db.reshape(1, -1), np.array([a_db]))[0]), 5),
            'crps_room_attempts': round(float(_crps(
                att.reshape(1, -1), np.array([a_att]))[0]), 5),
            'crps_room_pass_yards': round(float(_crps(
                yds.reshape(1, -1), np.array([a_yds]))[0]), 5),
            # THE DECOMPOSITION. Volume error and efficiency error are
            # reported side by side so a good yardage number produced by two
            # offsetting wrong components cannot pass as mechanistic success.
            'err_volume_dropbacks': round(float(db.mean()) - a_db, 4),
            'err_volume_attempts': round(float(att.mean()) - a_att, 4),
            'err_efficiency_ypa': (round(float(ypa[yi].mean()) - a_yds / a_att, 5)
                                   if a_att else ''),
            'err_final_pass_yards': round(float(yds.mean()) - a_yds, 4),
            'offsetting': int(bool(a_att) and (
                (float(att.mean()) - a_att) *
                (float(ypa[yi].mean()) - a_yds / a_att) < 0)),
        })
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--seasons', default=','.join(str(s) for s in EVAL_SEASONS))
    ap.add_argument('--draws', type=int, default=N_DRAWS)
    ap.add_argument('--out', default=None)
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args(argv)
    res = run(tuple(int(x) for x in a.seasons.split(',')), a.draws,
              out_dir=a.out, progress=not a.quiet)
    print(f'scored rows      : {len(res["rows"])}')
    print(f'diagnostic rows  : {len(res["diagnostics"])}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
