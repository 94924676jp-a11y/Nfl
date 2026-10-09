#!/usr/bin/env python3.12
"""Football accounting checks on the PUBLISHED Showdown worlds -- the arrays the optimizer scores. Read-only.

    python3.12 nfl/tools/world_accounting_check.py SCENARIO_DIR [--out REPORT.json]

QBCTX-C1 (owner directive 2026-10-08, after the independent Perplexity dependency audit at e8a2a3ae). The simulator
verifies its own identities on the RAW worlds (`identities_verified_by_the_simulator`), but the runner then applies
`classic_slate_run.efficiency_worlds` (independent per-player yard factors, interceptions drawn from a projection-level
rate) and the DST anchor step. A raw certificate says nothing about the arrays that are published afterwards. This
checks the published arrays (`*_WORLDS.npz`, `*_DRAWS.json`) themselves.

Each check is an ORDINARY-EVENT law from the NFL statistical definitions. A legitimate exception (a lateral after a
catch, a non-QB pass, a nullified play) can only excuse a violation where the world carries an event that represents
it. The Showdown simulator produces no lateral, non-QB-pass or penalty events, so no exception is available to any of
its worlds; that is recorded per check rather than assumed.

  PASS_YDS_EQ_REC_YDS    club gross passing yards == club receiving yards (tolerance: storage rounding)
  PASS_TD_EQ_REC_TD      club passing TDs == club receiving TDs
  TARGETS_LE_ATTEMPTS    club targets <= club pass attempts
  REC_LE_TARGETS         every player: receptions <= targets
  YDS_WITHOUT_CATCH      every player: receiving yards != 0 requires a reception
  REC_TD_WITHOUT_CATCH   every player: a receiving TD requires a reception
  INT_LE_ATTEMPTS        every passer: interceptions <= attempts
  INT_LE_OPP_TAKEAWAYS   club interceptions thrown <= the opposing DST's takeaways in the same world
  POINTS_GE_6_PER_TD     club points >= 6 x offensive TDs (points are a centred continuous draw, not event sums)
  INACTIVE_NO_EVENTS     an ordinary-OUT player records no events
  DK_FROM_PUBLISHED      the DK points the optimizer scores equal DK points recomputed from the published stat line

Nothing here changes a forecast. A violation is reported with counts and the first worlds, never repaired.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

SPEC_VERSION = 'world-accounting-1'
LATERAL_EVENTS_REPRESENTED = False      # the Showdown simulator has no lateral / non-QB pass / penalty event types


def dk_from_stats(pa, pyd, ptd, car, ryd, rtd, tgt, rec, recyd, rectd, ints):
    from nfl.tools.classic_slate_run import dk_from_stats as f
    return f(pa, pyd, ptd, car, ryd, rtd, tgt, rec, recyd, rectd, ints)


def load(sd: pathlib.Path):
    import numpy as np
    wp = next(sd.glob('*_WORLDS.npz'))
    dp = next(sd.glob('*_DRAWS.json'))
    z = np.load(wp, allow_pickle=False)
    meta = json.loads(z['meta'].tobytes())
    stats = z['stats'].astype('float64')
    for f in meta['yard_fields']:
        stats[:, :, meta['fields'].index(f)] /= meta['yard_scale']
    sp = next(sd.glob('*_STATE.json'), None)
    return meta, stats, z['points'].astype('float64'), json.loads(dp.read_text()), \
        (json.loads(sp.read_text()) if sp else None), {'worlds': wp.name, 'draws': dp.name}


def check(sd, max_examples=5):
    import numpy as np
    meta, S, pts, draws, state, files = load(pathlib.Path(sd))
    F = {f: i for i, f in enumerate(meta['fields'])}
    keys = meta['keys']
    club = np.array([k.rsplit('|', 1)[1] for k in keys])
    n_w = S.shape[1]
    tol_yd = 0.5 / meta['yard_scale']           # half a storage unit per player row
    out = {}

    def put(name, bad_mask, detail, exception='NONE_REPRESENTED', **kw):
        bad = np.flatnonzero(bad_mask)
        out[name] = {'violations': int(bad.size), 'of': int(bad_mask.size),
                     'first': [int(x) for x in bad[:max_examples]], 'detail': detail,
                     'legitimate_exception_available': exception, **kw}

    games = meta['games']
    # THE GAME INDEX, NOT THE FIRST GAME (2026-10-09). `points` is [game, world, (home, away)]; a Showdown file holds
    # one game so pts[0] was right there, but on a Classic file every club was compared with the first game's points.
    for gi, g in enumerate(games):
        for c, opp in ((g['home'], g['away']), (g['away'], g['home'])):
            m = club == c
            py = S[m, :, F['pass_yards']].sum(0)
            ry = S[m, :, F['rec_yards']].sum(0)
            tol = tol_yd * m.sum()
            d = py - ry
            put(f'{c}:PASS_YDS_EQ_REC_YDS', np.abs(d) > tol, 'gross passing minus receiving yards',
                mean_diff=round(float(d.mean()), 3), max_abs_diff=round(float(np.abs(d).max()), 2),
                tolerance=round(tol, 3))
            put(f'{c}:PASS_TD_EQ_REC_TD', S[m, :, F['pass_td']].sum(0) != S[m, :, F['rec_td']].sum(0),
                'passing TDs vs receiving TDs')
            put(f'{c}:TARGETS_LE_ATTEMPTS', S[m, :, F['targets']].sum(0) > S[m, :, F['pass_att']].sum(0),
                'club targets vs club pass attempts')
            ints = S[m, :, F['interceptions']].sum(0)
            dk = next((k for k in draws.get('dst_components', {}) if k.endswith('|' + opp)), None)
            if dk:
                take = np.array([w[1] for w in draws['dst_components'][dk]], dtype=float)
                put(f'{c}:INT_LE_OPP_TAKEAWAYS', ints > take,
                    f'interceptions thrown vs {dk} takeaways (raw DST components, before the anchor step)',
                    worlds_with_ints=int((ints > 0).sum()))
            col = 0 if c == g['home'] else 1
            td = (S[m, :, F['pass_td']].sum(0) + S[m, :, F['rush_td']].sum(0))
            put(f'{c}:POINTS_GE_6_PER_TD', pts[gi, :, col] + 1e-9 < 6 * td,
                'published club points vs 6 x offensive TDs in the same world')
    rec, tgt, recyd, rectd = (S[:, :, F[f]] for f in ('receptions', 'targets', 'rec_yards', 'rec_td'))
    put('REC_LE_TARGETS', (rec > tgt).any(0), 'any player with receptions > targets (per world)')
    put('YDS_WITHOUT_CATCH', ((np.abs(recyd) > tol_yd) & (rec == 0)).any(0),
        'any player with receiving yards and no reception (per world)',
        player_world_cells=int(((np.abs(recyd) > tol_yd) & (rec == 0)).sum()))
    put('REC_TD_WITHOUT_CATCH', ((rectd > 0) & (rec == 0)).any(0),
        'any player with a receiving TD and no reception (per world)',
        player_world_cells=int(((rectd > 0) & (rec == 0)).sum()))
    put('INT_LE_ATTEMPTS', (S[:, :, F['interceptions']] > S[:, :, F['pass_att']]).any(0),
        'any passer with more interceptions than attempts (per world)', exception='NOT_APPLICABLE')
    if state:
        out_names = {f"{p['name']}|{p['team']}" for p in state.get('players', {}).values()
                     if str((p.get('current_availability') or {}).get('status', '')).upper() in ('OUT', 'INACTIVE')}
        idx = [i for i, k in enumerate(keys) if k in out_names]
        active_ev = (np.abs(S[idx]).sum(2) > 0).any(0) if idx else np.zeros(n_w, bool)
        put('INACTIVE_NO_EVENTS', active_ev, f'{len(idx)} ordinary-OUT players carried in the worlds',
            exception='NOT_APPLICABLE', out_players_in_worlds=[keys[i] for i in idx])
    # DK points the optimizer scores vs DK recomputed from the published stat line. Yards are stored to 0.1, so a
    # world whose true yards sit just under a DK bonus line (100 rush/rec, 300 pass) can be stored AT the line: the
    # recomputation then differs by exactly the bonus. Such a cell counts only if no line within half a storage unit
    # of the stored yards reproduces the scored value.
    yi = [F[f] for f in meta['yard_fields']]
    half = 0.5 / meta['yard_scale']
    gap, n, rounding, bad = [], 0, 0, 0
    for i, k in enumerate(keys):
        dd = draws.get('draws', {}).get(k)
        if dd is None:
            continue
        n += 1
        for w in range(n_w):
            v = S[i, w]
            g = abs(dk_from_stats(*v) - dd[w])
            if g <= 0.06:
                continue
            alts = []
            for j in yi:
                for eps in (-half, half):
                    u = v.copy()
                    u[j] += eps
                    alts.append(abs(dk_from_stats(*u) - dd[w]))
            if min(alts) <= 0.06:
                rounding += 1
            else:
                bad += 1
                gap.append((k, w, round(g, 3)))
    out['DK_FROM_PUBLISHED'] = {'players': n, 'violations': bad, 'of': n * n_w,
                                'bonus_line_storage_rounding_cells': rounding, 'first': gap[:max_examples],
                                'detail': 'player-world cells whose scored DK is not reproduced by the published stat '
                                          'line within 0.06 points and half a yard-storage unit'}
    n_bad = {k: v['violations'] for k, v in out.items() if v['violations']}
    return {'ARTIFACT': 'WORLD_ACCOUNTING_CHECK', 'spec_version': SPEC_VERSION, 'scenario_dir': str(sd),
            'files': files, 'n_worlds': n_w, 'stage': 'PUBLISHED (after efficiency_worlds and the DST anchor step)',
            'lateral_or_non_qb_pass_events_represented': LATERAL_EVENTS_REPRESENTED,
            'VIOLATED': n_bad, 'checks': out,
            'READING': 'a violation is a published world that breaks an ordinary-event law with no represented '
                       'exception. It is a correctness finding about the incumbent, not a gate (no gate is changed).'}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('scenario_dir')
    ap.add_argument('--out')
    a = ap.parse_args(argv)
    r = check(pathlib.Path(a.scenario_dir))
    if a.out:
        pathlib.Path(a.out).write_text(json.dumps(r, indent=1) + '\n')
    print(json.dumps({'VIOLATED': r['VIOLATED']}, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
