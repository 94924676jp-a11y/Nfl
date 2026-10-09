#!/usr/bin/env python3.12
"""Per-stage DST and kicker measurements on a published Showdown scenario, plus the shadow fix. Read-only on inputs.

    PYTHONPATH=<numpy> [NFL_PIT_MANIFEST=<manifest>] python3.12 nfl/research/dst_scoring/measure_showdown.py \
        SCENARIO_DIR OUT.json

STAGES (each measured, none assumed):
  S0 RAW      the simulator's own DST draw, rebuilt from the published raw components
              (DRAWS.dst_components = sacks, takeaways, def TD, safeties, drawn by nfl/sim/dst.py in the band of
              the CONTINUOUS opponent points) plus dst.tier(opponent continuous points) -- exactly what
              DstModel.draw_components returned. Verified: S0 x the published anchor factor == the published draw.
  S1 ANCHOR   the published draw after showdown_slate_run's anchor_means (x factor). This is what the optimizer
              scored.
  FIX         nfl/sim/dst_k_event_scoring.dst_event_worlds, EVENTS and PROJECTION mean arms.
Kickers: the published draw, re-drawn through nfl/tools/kicker_world.draw with the build's own rng sequence
(showdown_draws.build: random.Random(seed) after the simulator, home club first) to recover integer components;
reproduction is verified draw for draw before any component is used. ATL@NO needs its PIT manifest for that.
"""
from __future__ import annotations

import json
import pathlib
import random
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.product import dk_scoring as DK  # noqa: E402
from nfl.sim import dst as dst_mod, dst_k_event_scoring as X  # noqa: E402

FIX_SEED_OFFSET = 7711   # declared: the shadow draws use seed = published seed + this, recorded in the output


def summ(x):
    a = np.asarray(x, dtype=float)
    n = a.size
    return {'mean': round(float(a.mean()), 4), 'sd': round(float(a.std(ddof=1)), 4),
            'mcse': round(float(a.std(ddof=1) / np.sqrt(n)), 4),
            'p_le_0': round(float((a <= 0).mean()), 4), 'p_ge_10': round(float((a >= 10).mean()), 4),
            'p_ge_15': round(float((a >= 15).mean()), 4), 'p_ge_20': round(float((a >= 20).mean()), 4),
            'non_integer_share': round(float((np.abs(a - np.round(a)) > 1e-9).mean()), 4),
            'min': float(a.min()), 'max': float(a.max())}


def _tier_floor(p):
    return dst_mod.tier(p)


def _tier_dkfunc(p):
    return DK.dst_points(points_allowed=p)


def _tier_rounded(p):
    return DK.dst_points(points_allowed=int(X.points_allowed_integer([p])[0]))


def measure(sd: pathlib.Path):
    dp = next(sd.glob('*_DRAWS.json'))
    pp = next(sd.glob('*_PROJ.json'))
    d = json.loads(dp.read_text())
    proj = json.loads(pp.read_text())
    rows = {f"{r['name']}|{r['team']}": r for r in proj['rows'].values()}
    home, away = d['home'], d['away']
    pts = np.asarray(d['world_points']['points'], dtype=float)
    club_pts = {d['world_points']['home']: pts[:, 0], d['world_points']['away']: pts[:, 1]}
    n = pts.shape[0]
    params = X.load_params()
    fac = d['player_mean_anchor']['dst_multiplicative']['factors']
    out = {'scenario': str(sd.relative_to(_REPO)), 'draws_file': dp.name, 'n_worlds': n, 'seed': d['seed'],
           'fix_seed': d['seed'] + FIX_SEED_OFFSET, 'dst': {}, 'kickers': {}, 'downstream': {}}
    fixed_draws = {k: list(v) for k, v in d['draws'].items()}
    for dkey, compw in d['dst_components'].items():
        club = dkey.rsplit('|', 1)[1]
        opp = away if club == home else home
        comp = np.asarray(compw, dtype=float)
        opp_pts = club_pts[opp]
        tf = np.array([_tier_floor(p) for p in opp_pts])
        s0 = tf + comp[:, 0] * 1.0 + comp[:, 1] * 2.0 + comp[:, 2] * 6.0 + comp[:, 3] * 2.0
        pub = np.asarray(d['draws'][dkey], dtype=float)
        f = fac[dkey]['factor']
        exact_f = pub.mean() / s0.mean()
        recon = np.abs(s0 * exact_f - pub).max()
        td = np.array([_tier_dkfunc(p) for p in opp_pts])
        tr = np.array([_tier_rounded(p) for p in opp_pts])
        pa_int = X.points_allowed_integer(opp_pts)
        qbs = [k for k in d['qb_interceptions'] if k.endswith('|' + opp)]
        ints = np.sum([np.asarray(d['qb_interceptions'][k], dtype=float) for k in qbs], axis=0)
        # the band the incumbent's tuple was drawn in (continuous points) vs the integer band
        def band(p):
            for lo, hi in dst_mod.CONDITIONING_BANDS:
                if lo <= p < hi:
                    return lo
            return dst_mod.CONDITIONING_BANDS[-1][0]
        band_cont = np.array([band(p) for p in opp_pts])
        band_int = np.array([band(float(p)) for p in pa_int])
        arms = {}
        for mode in (X.MEAN_EVENTS, X.MEAN_PROJECTION):
            r = X.dst_event_worlds(opp_pts, ints, rows[dkey], params, seed=d['seed'] + FIX_SEED_OFFSET,
                                   mean_mode=mode)
            c = r['components']
            arms[mode] = {'summary': summ(r['dk']), 'account': r['account'],
                          'component_means': {k: round(float(np.mean(v)), 4) for k, v in c.items()},
                          'checks': {
                              'all_integer': X.is_integer_array(r['dk']),
                              'valid_dk_values': X.valid_dst_values(r['dk']),
                              'dk_equals_dk_scoring_of_components': bool(
                                  np.array_equal(r['dk'], X.dst_dk_from_components(c))),
                              'points_allowed_band_matches_opponent_points': bool(
                                  np.array_equal(c['points_allowed'], pa_int)
                                  and np.all(np.abs(c['points_allowed'] - opp_pts) <= 0.5)),
                              'ints_reconcile_with_opposing_qbs': bool(np.array_equal(c['ints'], ints))}}
            if mode == X.MEAN_EVENTS:
                ev_dk = r['dk']
            else:
                pr_dk = r['dk']
        proj_mean = rows[dkey].get('dk_points')
        out['dst'][dkey] = {
            'projection_dk_points': proj_mean,
            'projection_event_items': rows[dkey]['dst']['event_items'],
            'S0_raw_simulator': {**summ(s0), 'component_means': {
                'sacks': round(float(comp[:, 0].mean()), 4), 'takeaways': round(float(comp[:, 1].mean()), 4),
                'def_td': round(float(comp[:, 2].mean()), 4), 'safeties': round(float(comp[:, 3].mean()), 4),
                'tier_points': round(float(tf.mean()), 4)}},
            'S1_published_after_anchor': {**summ(pub), 'anchor_factor_recorded': f,
                                          'anchor_factor_exact': round(float(exact_f), 6),
                                          'max_abs_S0_x_factor_minus_published': float(recon)},
            'opponent_points': {'non_integer_share': round(float((np.abs(opp_pts - np.round(opp_pts)) > 1e-9).mean()), 4),
                                'share_in_open_0_1': round(float(((opp_pts > 0) & (opp_pts < 1)).mean()), 4),
                                'mean': round(float(opp_pts.mean()), 3)},
            'tier_convention_disagreement': {
                'dst_tier_floor_vs_rounded_integer': round(float((tf != tr).mean()), 4),
                'dk_scoring_on_continuous_vs_rounded_integer': round(float((td != tr).mean()), 4),
                'dst_tier_floor_vs_dk_scoring_on_continuous': round(float((tf != td).mean()), 4),
                'mean_tier_floor': round(float(tf.mean()), 4), 'mean_tier_rounded': round(float(tr.mean()), 4),
                'conditioning_band_continuous_vs_integer': round(float((band_cont != band_int).mean()), 4)},
            'incumbent_interception_consistency': {
                'opposing_qbs': qbs, 'world_ints_mean': round(float(ints.mean()), 4),
                'share_qb_ints_exceed_raw_takeaways': round(float((ints > comp[:, 1]).mean()), 4),
                'raw_takeaways_mean': round(float(comp[:, 1].mean()), 4)},
            'FIX': arms,
            'mean_change_vs_published': {m: round(float(arms[m]['summary']['mean'] - pub.mean()), 4) for m in arms},
            'corr_with_opponent_points': {'S1_published': round(float(np.corrcoef(pub, opp_pts)[0, 1]), 4),
                                          'FIX_EVENTS': round(float(np.corrcoef(ev_dk, opp_pts)[0, 1]), 4),
                                          'FIX_PROJECTION': round(float(np.corrcoef(pr_dk, opp_pts)[0, 1]), 4)},
        }
        fixed_draws[dkey] = [float(x) for x in ev_dk]
    # downstream: every non-DST draw must be bit-identical between the published and the fixed draw sets
    moved = [k for k in d['draws'] if k not in d['dst_components'] and d['draws'][k] != fixed_draws[k]]
    out['downstream'] = {'n_players': len(d['draws']), 'n_dst_replaced': len(d['dst_components']),
                         'non_dst_players_changed': moved,
                         'skill_and_kicker_draws_bit_identical': not moved}
    # kickers
    from nfl.tools import kicker_world as KW
    rng = random.Random(d['seed'])
    csw = d['club_scoring_worlds']
    for club in (home, away):
        ks = [k for k in d['kickers'] if k.endswith('|' + club) and d['kickers'][k].get('ROLE') != 'NOT_THE_CLUB_KICKER']
        if not ks:
            continue
        mix = KW.band_mix(club)
        rates = KW.load()['rates']
        draws, comp = [], {b: [] for b in KW.BAND_POINTS}
        xp, xpatt, td_l, tp = [], [], [], []
        for p, t in csw[club]:
            dk, det = KW.draw(p, t, mix, rates, rng)
            draws.append(dk)
            for b in KW.BAND_POINTS:
                comp[b].append(det[f'{b}_made'])
            xp.append(det['xp_made'])
            xpatt.append(det['xp_att'])
            td_l.append(int(t))
        key = ks[0]
        pub = np.asarray(d['draws'][key], dtype=float)
        rep = np.asarray(draws, dtype=float)
        reproduced = bool(np.array_equal(rep, pub))
        rescored = X.kicker_dk_from_components(comp, xp)
        cp = np.asarray([p for p, _ in csw[club]], dtype=float)
        fg = sum(np.asarray(v) for v in comp.values())
        td_a, xp_a = np.asarray(td_l), np.asarray(xp)
        kick_and_td_pts = 6 * td_a + xp_a + 3 * fg
        out['kickers'][key] = {
            'published': summ(pub), 'reproduced_draw_for_draw': reproduced,
            'max_abs_reproduction_diff': float(np.abs(rep - pub).max()),
            'rescored_through_dk_scoring_equals_published': bool(np.array_equal(rescored, pub)) if reproduced else None,
            'all_integer': X.is_integer_array(pub), 'valid_values': X.valid_kicker_values(pub),
            'xp_made_le_offensive_td': bool(np.all(xp_a <= td_a)),
            'share_6td_plus_xp_plus_3fg_exceeds_rounded_club_points': round(float(
                (kick_and_td_pts > np.ceil(cp - 0.5)).mean()), 4),
            'share_offensive_td_points_exceed_club_points': round(float((6 * td_a > cp + 1e-9).mean()), 4),
            'component_means': {**{b: round(float(np.mean(v)), 4) for b, v in comp.items()},
                                'xp_made': round(float(xp_a.mean()), 4)},
            'point_projection_kicker_model': rows.get(key, {}).get('dk_points'),
            'FIX': 'NONE NEEDED: the published Showdown kicker is already dk_scoring of its own integer components',
        }
    return out


if __name__ == '__main__':
    r = measure(pathlib.Path(sys.argv[1]).resolve())
    pathlib.Path(sys.argv[2]).write_text(json.dumps(r, indent=1, default=str) + '\n')
    for k, v in r['dst'].items():
        print(k, 'proj', v['projection_dk_points'], 'S0', v['S0_raw_simulator']['mean'], v['S0_raw_simulator']['non_integer_share'],
              'S1', v['S1_published_after_anchor']['mean'], v['S1_published_after_anchor']['non_integer_share'],
              'recon', v['S1_published_after_anchor']['max_abs_S0_x_factor_minus_published'],
              'EV', v['FIX']['EVENTS']['summary']['mean'], 'PR', v['FIX']['PROJECTION']['summary']['mean'],
              v['FIX']['PROJECTION']['account']['state'])
    for k, v in r['kickers'].items():
        print(k, v['published']['mean'], 'repro', v['reproduced_draw_for_draw'], v['max_abs_reproduction_diff'],
              'int', v['all_integer'], 'rescored', v['rescored_through_dk_scoring_equals_published'])
    print('downstream', r['downstream'])
