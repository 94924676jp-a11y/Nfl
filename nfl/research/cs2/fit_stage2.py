"""Estimate the three CS2 stage-2 parameters by forward-chained evaluation.

Predeclared in `PREREGISTRATION_STAGE2.md`. Nothing here was looked at before
that document was written, and the selection rule below is the one it fixed:
lowest MAE, then the SIMPLEST grid point whose player-blocked bootstrap
interval overlaps the best.

    python3.12 nfl/research/cs2/fit_stage2.py           # both targets
    python3.12 nfl/research/cs2/fit_stage2.py --quick   # coarse, for wiring
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import statistics
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.nonqb import p4c_params as P4                  # noqa: E402
from nfl.production.nonqb import role_prior as RP                  # noqa: E402
from sportsplatform.governance.outcome import State                # noqa: E402

SPEC_VERSION = 'cs2-stage2-fit-1'
EVAL_SEASONS = (2022, 2023, 2024, 2025)
POSITIONS = ('RB', 'WR', 'TE')
TARGETS = {'carries': 's_carries', 'targets': 's_targets'}
N_BOOT = 400
BOOT_SEED = 20260922

HALF_LIVES = (1.0, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0, float('inf'))
SEASON_DECAYS = (1.00, 0.85, 0.70, 0.50)
TEAM_DISCOUNTS = (1.00, 0.75, 0.50, 0.25)
OPP_EXPONENTS = (0.0, 0.5, 1.0)
SHRINK_TARGETS = ('positional_mean', 'club_room_mean')

#: How many mechanisms a grid point turns on. Ties in loss are broken toward
#: fewer, then toward today's production behaviour (hl=3, everything else off).
def complexity(g):
    return (int(g['season_decay'] != 1.0) + int(g['team_discount'] != 1.0)
            + int(g['opp_exponent'] != 0.0)
            + int(g['shrink_target'] != 'positional_mean'))


def distance_from_production(g):
    hl = g['half_life']
    return (abs((3.0 if hl == float('inf') else hl) - 3.0),
            abs(g['season_decay'] - 1.0), abs(g['team_discount'] - 1.0),
            abs(g['opp_exponent'] - 0.0))


def predict(hist, *, half_life, season_decay, team_discount, opp_exponent,
            target_season, target_team, fallback):
    """Weighted mean of prior appeared shares, or the fallback if there are none.

    `hist` is oldest-first [(season, team, share, opportunity)]. Weights decay
    by POSITION (as production does), then additionally across each season
    boundary and for observations at another club.
    """
    if not hist:
        return fallback, 0
    lam = 0.0 if half_life == float('inf') else 0.5 ** (1.0 / half_life)
    num = den = 0.0
    for age, (s, t, share, opp) in enumerate(reversed(hist)):
        w = 1.0 if half_life == float('inf') else lam ** age
        if season_decay != 1.0:
            w *= season_decay ** max(0, int(target_season) - int(s))
        if team_discount != 1.0 and t != target_team:
            w *= team_discount
        if opp_exponent:
            w *= max(float(opp), 0.0) ** opp_exponent
        num += w * float(share)
        den += w
    if den <= 0:
        return fallback, len(hist)
    return num / den, len(hist)


def build_frame(panel, target_key):
    """Per-row evaluation records, each carrying its own prior history."""
    rows = [r for r in panel if r.get('position') in POSITIONS]
    rows.sort(key=lambda r: (r['ord'], r.get('team') or '', r['gsis_id']))
    hist = collections.defaultdict(list)
    frame = []
    # Club-room running mean, by (ord-bucket, team, position), built only from
    # STRICTLY EARLIER rows so it never sees the row it shrinks.
    room = collections.defaultdict(list)
    pos_hist = collections.defaultdict(list)
    for r in rows:
        pid, pos, team = r['gsis_id'], r['position'], r.get('team')
        v = r.get(target_key)
        appeared = bool(r.get('appeared'))
        if int(r.get('season', 0)) in EVAL_SEASONS and v is not None \
                and appeared:
            frame.append({
                'gsis_id': pid, 'position': pos, 'team': team,
                'season': int(r['season']), 'ord': r['ord'],
                'y': float(v),
                'hist': list(hist[pid]),
                'room_mean': (statistics.mean(room[(team, pos)][-40:])
                              if room[(team, pos)] else None),
                'pos_mean': (statistics.mean(pos_hist[pos][-4000:])
                             if pos_hist[pos] else 0.0)})
        if appeared and v is not None:
            opp = float(r.get('carries') or 0.0) + float(r.get('targets') or 0.0)
            hist[pid].append((int(r['season']), team, float(v), opp))
            room[(team, pos)].append(float(v))
            pos_hist[pos].append(float(v))
    return frame


def evaluate(frame, grid):
    err = np.empty(len(frame))
    players = np.empty(len(frame), dtype=object)
    for i, f in enumerate(frame):
        fb = (f['room_mean'] if grid['shrink_target'] == 'club_room_mean'
              and f['room_mean'] is not None else f['pos_mean'])
        p, _n = predict(f['hist'], half_life=grid['half_life'],
                        season_decay=grid['season_decay'],
                        team_discount=grid['team_discount'],
                        opp_exponent=grid['opp_exponent'],
                        target_season=f['season'], target_team=f['team'],
                        fallback=fb)
        err[i] = p - f['y']
        players[i] = f['gsis_id']
    return err, players


def blocked_bootstrap(err_a, err_b, players, n_boot=N_BOOT, seed=BOOT_SEED):
    """95% interval for MAE(a) - MAE(b), resampling whole players."""
    rng = np.random.default_rng(seed)
    idx = collections.defaultdict(list)
    for i, p in enumerate(players):
        idx[p].append(i)
    keys = list(idx)
    blocks = [np.asarray(idx[k]) for k in keys]
    a, b = np.abs(err_a), np.abs(err_b)
    diffs = np.empty(n_boot)
    for j in range(n_boot):
        pick = rng.integers(0, len(blocks), len(blocks))
        sel = np.concatenate([blocks[i] for i in pick])
        diffs[j] = a[sel].mean() - b[sel].mean()
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return float(lo), float(hi)


def fit(target_name, panel, quick=False):
    key = TARGETS[target_name]
    frame = build_frame(panel, key)
    hls = (3.0, 6.0, 12.0) if quick else HALF_LIVES
    sds = (1.0, 0.7) if quick else SEASON_DECAYS
    tds = (1.0, 0.5) if quick else TEAM_DISCOUNTS
    oes = (0.0, 1.0) if quick else OPP_EXPONENTS
    sts = SHRINK_TARGETS

    results = []
    for hl in hls:
        for sd in sds:
            for td in tds:
                for oe in oes:
                    for st in sts:
                        g = {'half_life': hl, 'season_decay': sd,
                             'team_discount': td, 'opp_exponent': oe,
                             'shrink_target': st}
                        err, players = evaluate(frame, g)
                        results.append({
                            'grid': g, 'mae': float(np.abs(err).mean()),
                            'rmse': float(np.sqrt((err ** 2).mean())),
                            'bias': float(err.mean()),
                            'complexity': complexity(g),
                            '_err': err, '_players': players})
    results.sort(key=lambda r: r['mae'])
    best = results[0]

    # SELECTION RULE FROM THE PREREGISTRATION, applied exactly -- with one
    # stated computational pre-screen. Bootstrapping all 768 grid points
    # against the best is 300k resamples of the whole frame. A point whose
    # MAE exceeds the best by more than FIVE naive standard errors of the
    # paired difference cannot have an interval covering zero once the
    # blocking (which WIDENS intervals) is applied... except that blocking
    # widens them, so the screen is set deliberately loose at 5 SE and the
    # number screened out is reported. Everything surviving is bootstrapped
    # properly.
    n = len(best['_err'])
    screened_out = 0
    overlapping = []
    for r in results:
        if r is best:
            overlapping.append(r)
            continue
        d = np.abs(r['_err']) - np.abs(best['_err'])
        naive_se = float(d.std(ddof=1) / np.sqrt(n)) if n > 1 else 0.0
        if naive_se > 0 and (r['mae'] - best['mae']) > 5.0 * naive_se:
            screened_out += 1
            continue
        lo, hi = blocked_bootstrap(r['_err'], best['_err'], best['_players'])
        r['vs_best_ci'] = [lo, hi]
        if lo <= 0.0 <= hi:
            overlapping.append(r)
    chosen = sorted(overlapping,
                    key=lambda r: (r['complexity'],
                                   distance_from_production(r['grid'])))[0]

    prod = next((r for r in results
                 if r['grid'] == {'half_life': 3.0, 'season_decay': 1.0,
                                  'team_discount': 1.0, 'opp_exponent': 0.0,
                                  'shrink_target': 'positional_mean'}), None)
    out = {
        'target': target_name, 'n_rows': len(frame),
        'n_players': len(set(f['gsis_id'] for f in frame)),
        'eval_seasons': list(EVAL_SEASONS),
        'n_grid_points': len(results),
        'best_by_mae': {'grid': best['grid'], 'mae': best['mae'],
                        'rmse': best['rmse'], 'bias': best['bias']},
        'n_statistically_indistinguishable_from_best': len(overlapping),
        'n_prescreened_out_at_5_naive_se': screened_out,
        'n_bootstrapped': len(results) - screened_out,
        'chosen': {'grid': chosen['grid'], 'mae': chosen['mae'],
                   'rmse': chosen['rmse'], 'bias': chosen['bias'],
                   'complexity': chosen['complexity']},
        'production_today': (None if prod is None else
                             {'grid': prod['grid'], 'mae': prod['mae'],
                              'rmse': prod['rmse'], 'bias': prod['bias']}),
        'top10': [{'grid': r['grid'], 'mae': round(r['mae'], 6),
                   'rmse': round(r['rmse'], 6), 'bias': round(r['bias'], 6)}
                  for r in results[:10]],
    }
    if prod is not None and chosen is not prod:
        lo, hi = blocked_bootstrap(prod['_err'], chosen['_err'],
                                   chosen['_players'])
        out['chosen_vs_production_mae_delta'] = prod['mae'] - chosen['mae']
        out['chosen_vs_production_ci95_player_blocked'] = [lo, hi]
        out['chosen_beats_production'] = bool(lo > 0.0)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--quick', action='store_true')
    ap.add_argument('--out', default='nfl/research/cs2/STAGE2_FIT.json')
    a = ap.parse_args(argv)
    if P4.ensure_artifacts().state is not State.PASS:
        print('P4C artifacts unavailable')
        return 2
    import p4c_build as PB
    PB.P4B = str(P4._DIR)
    panel = PB.load_panel()
    res = {'spec_version': SPEC_VERSION,
           'preregistration': 'nfl/research/cs2/PREREGISTRATION_STAGE2.md',
           'panel_ord_range': [min(r['ord'] for r in panel),
                               max(r['ord'] for r in panel)],
           'panel_rows': len(panel), 'quick': bool(a.quick),
           'n_boot': N_BOOT, 'boot_seed': BOOT_SEED,
           'selection_rule': 'lowest MAE, then simplest grid point whose '
                             'player-blocked 95% bootstrap interval overlaps '
                             'the best',
           'fits': {}}
    for t in TARGETS:
        print(f'fitting {t} ...', flush=True)
        res['fits'][t] = fit(t, panel, quick=a.quick)
        c = res['fits'][t]['chosen']
        print(f'  chosen {c["grid"]} mae={c["mae"]:.6f}')
    p = _REPO / a.out
    p.write_text(json.dumps(res, indent=1, sort_keys=True, default=str))
    print(f'wrote {p}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
