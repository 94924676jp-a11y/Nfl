#!/usr/bin/env python3.12
"""Per-stage DST measurements on the Classic Week-5 research run, plus the shadow fix. Read-only on inputs.

    PYTHONPATH=<numpy> python3.12 nfl/research/dst_scoring/measure_classic.py RESEARCH_STATE_DIR OUT.json [WORK_DIR]

The published Classic DRAWS keep neither the per-world club points nor the raw DST components nor the QB
interceptions, so the run is REPLAYED, exactly as nfl/tools/classic_slate_run.run does it (one
showdown_draws.build per game, seed SEED + i in sorted game order, projection-centred volume, n_calib = n_sims,
then efficiency_worlds over the merged stat worlds with seed SEED + 99, then anchor_means on the rest). The replay
is accepted only if every published draw is reproduced; otherwise the script refuses with the worst difference.
"""
from __future__ import annotations

import gzip
import json
import pathlib
import sys
import tempfile

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.sim import dst as dst_mod, dst_k_event_scoring as X  # noqa: E402
from nfl.research.dst_scoring.measure_showdown import summ, FIX_SEED_OFFSET  # noqa: E402


def replay(rs: pathlib.Path, work: pathlib.Path):
    from nfl.tools import classic_slate_run as CR, showdown_draws as SD
    from nfl.sim import game as sim_game
    work.mkdir(parents=True, exist_ok=True)
    pub = json.loads(gzip.open(rs / 'DRAWS.json.gz').read())
    proj_p = work / 'PROJ.json'
    proj_p.write_bytes(gzip.open(rs / 'PROJ.json.gz').read())
    proj = json.loads(proj_p.read_text())
    state = json.loads((rs / 'STATE.json').read_text())
    n_sims = pub['n_sims']
    merged, stats_all, worlds, dstc = {}, {}, {}, {}
    for i, (gid, g) in enumerate(sorted(state['games'].items())):
        away, home = g['away'], g['home']
        if pub['per_game'][gid]['seed'] != CR.SEED + i:
            raise RuntimeError(f'CLASSIC_REPLAY_SEED_MISMATCH {gid}')
        sl = {'game_id': gid, 'away': away, 'home': home, 'week': state['week'], 'season': state['season'],
              'kickoff_et_naive': state['kickoff'],
              'environment': {'games': {f'{away}@{home}': state['environment']['games'][f'{away}@{home}']}}}
        sp = work / f'{gid}.state.json'
        sp.write_text(json.dumps(sl))
        SD.OUT = work / f'{gid}.draws.json'
        o = SD.build(str(proj_p), str(sp), n_sims=n_sims, seed=CR.SEED + i,
                     volume_centre=sim_game.VOLUME_CENTRE_PROJECTION, n_calib=n_sims)
        if o.state.value != 'PASS':
            raise RuntimeError(f'CLASSIC_REPLAY_GAME_REFUSED {gid} {o.code} {o.detail}')
        art = o.value
        for k, v in art['draws'].items():
            merged[k] = v
        stats_all.update(art['stat_draws'])
        wp = art['world_points']
        worlds[gid] = {'home': home, 'away': away, 'points': np.asarray(wp['points'], dtype=float)
                       if isinstance(wp, dict) else np.asarray(wp, dtype=float)}
        dstc.update(art['dst_components'] or {})
        print('replayed', gid, flush=True)
    rows_by_key = {SD.S.player_key(r['name'], r['team']): r for r in proj['rows'].values()}
    targets = {k: r.get('dk_points') for k, r in rows_by_key.items() if isinstance(r.get('dk_points'), (int, float))}
    raw = {k: list(v) for k, v in merged.items()}
    dk_new, stat_worlds, _eff = CR.efficiency_worlds(stats_all, rows_by_key, float(proj['int_rate']), CR.SEED + 99)
    merged = {**merged, **dk_new}
    rest = {k: v for k, v in merged.items() if k not in dk_new}
    rest, acc = CR.anchor_means(rest, targets)
    merged.update(rest)
    worst = max(float(np.abs(np.asarray(merged[k]) - np.asarray(pub['draws'][k])).max()) for k in pub['draws'])
    missing = sorted(set(pub['draws']) ^ set(merged))
    return pub, proj, rows_by_key, raw, merged, stat_worlds, worlds, dstc, worst, missing, acc


def measure(rs, work):
    pub, proj, rows, raw, merged, stat_worlds, worlds, dstc, worst, missing, acc = replay(rs, work)
    out = {'research_state': str(rs), 'n_worlds': pub['n_sims'], 'replay_worst_abs_diff': worst,
           'replay_key_mismatch': missing, 'REPRODUCED': worst == 0.0 and not missing, 'dst': {}}
    if not out['REPRODUCED']:
        return out
    params = X.load_params()
    fixed = {k: list(v) for k, v in merged.items()}
    for gid, w in worlds.items():
        pts = {w['home']: w['points'][:, 0], w['away']: w['points'][:, 1]}
        for club, opp in ((w['home'], w['away']), (w['away'], w['home'])):
            dkey = next((k for k in dstc if k.endswith('|' + club)), None)
            if dkey is None:
                continue
            comp = np.asarray(dstc[dkey], dtype=float)
            opp_pts = pts[opp]
            tf = np.array([dst_mod.tier(p) for p in opp_pts])
            s0 = tf + comp[:, 0] + 2 * comp[:, 1] + 6 * comp[:, 2] + 2 * comp[:, 3]
            if not np.array_equal(s0, np.asarray(raw[dkey], dtype=float)):
                raise RuntimeError(f'CLASSIC_S0_RECONSTRUCTION_FAILED {dkey}')
            qbs = [k for k, r in rows.items() if r.get('team') == opp and r.get('position') == 'QB' and k in stat_worlds]
            ints = np.sum([np.asarray([x[10] for x in stat_worlds[k]], dtype=float) for k in qbs], axis=0)
            arms = {}
            for mode in (X.MEAN_EVENTS, X.MEAN_PROJECTION):
                seed = pub['per_game'][gid]['seed'] + FIX_SEED_OFFSET + (0 if club == w['home'] else 1)
                r = X.dst_event_worlds(opp_pts, ints, rows[dkey], params, seed=seed, mean_mode=mode)
                c = r['components']
                arms[mode] = {'summary': summ(r['dk']), 'account': r['account'], 'checks': {
                    'all_integer': X.is_integer_array(r['dk']), 'valid_dk_values': X.valid_dst_values(r['dk']),
                    'dk_equals_dk_scoring_of_components': bool(np.array_equal(r['dk'], X.dst_dk_from_components(c))),
                    'points_allowed_band_matches_opponent_points': bool(np.all(np.abs(c['points_allowed'] - opp_pts) <= 0.5)),
                    'ints_reconcile_with_opposing_qbs': bool(np.array_equal(c['ints'], ints))}}
                if mode == X.MEAN_EVENTS:
                    fixed[dkey] = [float(x) for x in r['dk']]
            p1 = np.asarray(merged[dkey], dtype=float)
            out['dst'][dkey] = {'game': gid, 'projection_dk_points': rows[dkey].get('dk_points'),
                                'S0_raw_simulator': summ(s0), 'S1_published_after_anchor': summ(p1),
                                'anchor_factor': acc['factors'][dkey]['factor'],
                                'world_ints_mean': round(float(ints.mean()), 4),
                                'share_qb_ints_exceed_raw_takeaways': round(float((ints > comp[:, 1]).mean()), 4),
                                'FIX': arms,
                                'mean_change_vs_published': {m: round(arms[m]['summary']['mean'] - float(p1.mean()), 4)
                                                             for m in arms}}
    moved = [k for k in merged if k not in out['dst'] and merged[k] != fixed[k]]
    out['downstream'] = {'n_players': len(merged), 'n_dst_replaced': len(out['dst']),
                         'non_dst_players_changed': moved, 'skill_draws_bit_identical': not moved}
    return out


if __name__ == '__main__':
    rs = pathlib.Path(sys.argv[1])
    work = pathlib.Path(sys.argv[3]) if len(sys.argv) > 3 else pathlib.Path(tempfile.mkdtemp(prefix='dst_classic_'))
    r = measure(rs, work)
    pathlib.Path(sys.argv[2]).write_text(json.dumps(r, indent=1, default=str) + '\n')
    print('REPRODUCED', r['REPRODUCED'], r['replay_worst_abs_diff'], r['replay_key_mismatch'][:5])
    for k, v in r['dst'].items():
        print(f"{k:14s} proj {v['projection_dk_points']:.3f} S0 {v['S0_raw_simulator']['mean']:.3f} "
              f"nonint {v['S0_raw_simulator']['non_integer_share']} S1 {v['S1_published_after_anchor']['mean']:.3f} "
              f"nonint {v['S1_published_after_anchor']['non_integer_share']} EV {v['FIX']['EVENTS']['summary']['mean']:.3f} "
              f"PR {v['FIX']['PROJECTION']['summary']['mean']:.3f} {v['FIX']['PROJECTION']['account']['state']}")
    print(r.get('downstream'))
