#!/usr/bin/env python3.12
"""One classic slate, end to end through the football layers: role state -> projection -> joint draws.

    python3.12 nfl/tools/classic_slate_run.py 2026W4 [--n-sims 2000]

WHY THIS EXISTS. The Week-3 chain pins its files and its week as module constants, and the Week-4
showdown drove the same modules by setting those constants programmatically. This is that route,
parameterised by slate and written down, so a new slate is an argument and not an edit.

WHAT IT SETS, AND WHY EACH IS A DECISION RATHER THAN A DEFAULT
  proj_v1.MARKET_ARM = 'FOOTBALL_ONLY'   owner production contract 2026-10-03: sportsbook spread,
                                         total and implied totals are PROHIBITED proprietary inputs.
                                         The incumbent 'MARKET' arm feeds implied totals into the TD
                                         pool and the DST centre, so it cannot be the proprietary
                                         number. FOOTBALL_ONLY is the declared candidate arm
                                         (PROGRAM-4); it is NOT validated, and the artifact says so.
  volume_centre = 'projection'           the projection-centred simulator arm (owner ruling
                                         2026-10-02), so the draws reconcile to the projection
                                         rather than to a regression on implied points
  proj_v1.SLATE_WEEK = state['week']     read from the slate state, never typed

Draws are per game (independent seeds) and merged on one world index: games on a classic slate are
simulated independently, and that independence is stated in the artifact, not implied.

It fits nothing, fetches nothing, and never reads the FantasyCruncher file or a Hard Rock price.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

OUT_DIR = _REPO / 'nfl/dfs/salaries'
SEED = 20261004


#: DECLARED STEP (2026-10-03), switchable with --player-mean-anchor none. The projection-centred arm
#: reconciles CLUB volume only; inside the club the simulator gives every player league-average
#: yards per target and per carry (nfl/sim/game.py USAGE_FIRST: club draw + league player deviation,
#: no player centre). Measured on week 4 before this step: simulated mean minus projection ranged
#: from -5.95 (Zay Flowers) to +3.33 (Jalon Daniels), against a Monte Carlo SE near 0.2, so the
#: portfolio was optimising on numbers our own board disagreed with. Owner ruling 2026-10-02: the
#: projection is the expected-value centre and the simulator adds dispersion around it. This step
#: rescales each player's draws so their mean is his unconditional dk_points. A positive rescale leaves
#: every between-player correlation unchanged and keeps each player's coefficient of variation.
#: It is not a fix for the simulator's missing player efficiency, which needs the projection's
#: club passing yards to close first (it does not: CHI receivers +38 yds over the QB, PHI -39).
ANCHOR_PROJECTION = 'PROJECTION_MEAN_MULTIPLICATIVE'
ANCHOR_NONE = 'NONE'
#: DEFAULT (2026-10-03, supersedes the multiplicative step the same evening). Football first: the
#: simulator's volumes are already the projection's (club volume reconciled, player shares from the
#: projection), so what is missing is EFFICIENCY. In every world each player's receiving, rushing and
#: passing yards are rescaled by one per-player factor so their mean is his projected conditional
#: yards PER OPPORTUNITY; interceptions, which the simulator never draws, are drawn Binomial(world attempts, the
#: projection's measured int_rate); DK points are recomputed from that stat line with the
#: simulator's own scoring. Volumes, catches and touchdowns are left exactly as simulated, so the
#: residual DK gap left over is the touchdown and bonus disagreement, reported and not hidden.
#: DST has no stat line here and keeps the multiplicative step.
ANCHOR_EFFICIENCY = 'PROJECTION_EFFICIENCY_PER_WORLD'
#: A per-opportunity ratio needs opportunities to be measured on. DERIVATION, not a fit: yards per
#: target has a spread near 8-10 yds, so 30 simulated opportunities put the simulated rate's SE near
#: 1.6 yds, about 20% of a typical rate. Below 30 across all worlds the factor is left at 1 and the
#: player is named; on week 4 every such player averages under 0.05 opportunities per world.
MIN_SIM_OPPORTUNITIES = 30
STAT_FIELDS = ('pass_att', 'pass_yards', 'pass_td', 'carries', 'rush_yards', 'rush_td',
               'targets', 'receptions', 'rec_yards', 'rec_td')


def dk_from_stats(pa, pyd, ptd, car, ryd, rtd, tgt, rec, recyd, rectd, ints):
    """DraftKings Classic scoring, identical to nfl/sim/game.py's, plus interceptions."""
    return (pyd * 0.04 + ptd * 4.0 + (3.0 if pyd >= 300 else 0.0) - ints
            + ryd * 0.1 + rtd * 6.0 + (3.0 if ryd >= 100 else 0.0)
            + rec * 1.0 + recyd * 0.1 + rectd * 6.0 + (3.0 if recyd >= 100 else 0.0))


def efficiency_worlds(stat_draws: dict, rows_by_key: dict, int_rate: float, seed: int):
    """Per-world stat lines re-centred on the projection's efficiency, and DK points from them.

    stat_draws: {key: [10-tuple in STAT_FIELDS order] per world}. rows_by_key: projection rows.
    Returns (dk draws, stat worlds with 'ints' appended, account).
    """
    import random as _r
    rng = _r.Random(seed)
    dk, worlds, factors, left = {}, {}, {}, {}
    idx = {f: i for i, f in enumerate(STAT_FIELDS)}
    for k, v in stat_draws.items():
        r = rows_by_key.get(k)
        if r is None:
            left[k] = 'NO_PROJECTION_ROW'
            continue
        cv = r.get('conditional_volume') or {}
        f = {}
        # PER OPPORTUNITY, never per game: the factor is projected yards per target (carry, attempt)
        # over simulated yards per target (carry, attempt). A total-yards ratio would mix in the
        # appearance process -- a backup's conditional 200 passing yards against his near-zero
        # simulated volume gives a factor near 100 on the few worlds he throws.
        for fld, opp in (('rec_yards', 'targets'), ('rush_yards', 'carries'), ('pass_yards', 'pass_att')):
            vol_src = 'pass_attempts' if opp == 'pass_att' else opp
            sim_y = sum(w[idx[fld]] for w in v)
            sim_o = sum(w[idx[opp]] for w in v)
            ty, to = cv.get(fld), cv.get(vol_src)
            if (isinstance(ty, (int, float)) and isinstance(to, (int, float)) and to > 0 and ty >= 0
                    and sim_o >= MIN_SIM_OPPORTUNITIES and sim_y > 0):
                f[fld] = (ty / to) / (sim_y / sim_o)
            else:
                f[fld] = 1.0
                if isinstance(ty, (int, float)) and ty > 0.5:
                    left.setdefault(k, []).append(
                        f'{fld}: simulated {sim_y / len(v):.3f} yds on {sim_o / len(v):.3f} {opp} per world; '
                        f'projection {ty:.2f} yds on {to if isinstance(to, (int, float)) else to} {vol_src}')
        factors[k] = {x: round(y, 4) for x, y in f.items()}
        out, d = [], []
        for w in v:
            pa, pyd, ptd, car, ryd, rtd, tgt, rec, recyd, rectd = w
            pyd, ryd, recyd = pyd * f['pass_yards'], ryd * f['rush_yards'], recyd * f['rec_yards']
            n = int(round(pa))
            ints = sum(1 for _ in range(n) if rng.random() < int_rate) if n > 0 else 0
            out.append((pa, pyd, ptd, car, ryd, rtd, tgt, rec, recyd, rectd, ints))
            d.append(dk_from_stats(pa, pyd, ptd, car, ryd, rtd, tgt, rec, recyd, rectd, ints))
        worlds[k], dk[k] = out, d
    return dk, worlds, {'n_players': len(worlds), 'factors': factors, 'not_anchorable': left}


def anchor_means(draws: dict, targets: dict) -> tuple[dict, dict]:
    """Rescale each player's draws to his target mean. Returns (new draws, account).

    A player is left as drawn, and named in the account, when he has no target or his simulated
    mean is not positive (no rescale can move a zero-centred distribution to a positive mean).
    """
    out, factors, left = {}, {}, {}
    for k, v in draws.items():
        t = targets.get(k)
        m = sum(v) / len(v) if v else 0.0
        if t is None:
            out[k], left[k] = v, 'NO_PROJECTION_TARGET'
            continue
        if m <= 0:
            out[k], left[k] = v, f'SIMULATED_MEAN_NOT_POSITIVE ({m:.3f})'
            continue
        f = float(t) / m
        out[k] = [x * f for x in v]
        factors[k] = {'factor': round(f, 4), 'raw_mean': round(m, 3), 'target': round(float(t), 3)}
    return out, {'n_anchored': len(factors), 'n_left_as_drawn': len(left), 'left_as_drawn': left,
                 'factors': factors}


def paths(slate_id):
    return {'state': OUT_DIR / f'DK_{slate_id}_EARLY_STATE.json',
            'proj': OUT_DIR / f'DK_{slate_id}_EARLY_PROJ.json',
            'draws': OUT_DIR / f'DK_{slate_id}_EARLY_DRAWS.json',
            'worlds': OUT_DIR / f'DK_{slate_id}_EARLY_WORLDS.npz'}


#: Yards are stored in tenths of a yard as int16 (range +-3276.7 yds), counts exactly.
WORLD_FIELDS = STAT_FIELDS + ('interceptions',)
YARD_FIELDS = ('pass_yards', 'rush_yards', 'rec_yards')


def _write_worlds(path, stat_worlds, game_worlds, projection_sha):
    import numpy as np
    keys = sorted(stat_worlds)
    n = len(next(iter(stat_worlds.values())))
    arr = np.zeros((len(keys), n, len(WORLD_FIELDS)), dtype=np.int16)
    for i, k in enumerate(keys):
        a = np.asarray(stat_worlds[k], dtype=float)
        for j, f in enumerate(WORLD_FIELDS):
            arr[i, :, j] = np.rint(a[:, j] * (10 if f in YARD_FIELDS else 1))
    gids = sorted(game_worlds)
    pts = np.asarray([game_worlds[g]['world_points']['points'] for g in gids], dtype=np.float32)
    meta = {'keys': keys, 'fields': WORLD_FIELDS, 'yard_scale': 10, 'yard_fields': YARD_FIELDS,
            'games': [{'game_id': g, 'home': game_worlds[g]['world_points']['home'],
                       'away': game_worlds[g]['world_points']['away']} for g in gids],
            'projection_sha256': projection_sha,
            'MEANING': 'per-world stat lines after the efficiency step, and each game\'s simulated score'}
    with open(path, 'wb') as fh:
        np.savez_compressed(fh, stats=arr, points=pts, meta=np.frombuffer(json.dumps(meta).encode(), dtype=np.uint8))


def load_worlds(path):
    """(stats int16 [player, world, field], points float32 [game, world, (home, away)], meta)."""
    import numpy as np
    z = np.load(path)
    return z['stats'], z['points'], json.loads(bytes(z['meta']).decode())


def run(slate_id: str, *, n_sims: int = 2000, player_mean_anchor: str = ANCHOR_EFFICIENCY) -> Outcome:
    from nfl.tools import proj_v1 as PV, role_state as RS, showdown_draws as SD, football_sanity as FS
    from nfl.sim import game as sim_game
    P = paths(slate_id)
    if not P['state'].exists():
        return Outcome.blocked('CLASSIC_RUN_NO_STATE', f'{P["state"].name} not built', cause=Cause.DATA)
    state = json.loads(P['state'].read_text())

    # 1. ROLE STATE from this slate's players.
    RS.POST = P['state']
    rs = RS.run()
    if rs.state.value != 'PASS':
        return rs

    # 2. PROJECTION, football-only arm, this slate's week.
    PV.POST, PV.OUT, PV.SLATE_WEEK = P['state'], P['proj'], int(state['week'])
    PV.MARKET_ARM = 'FOOTBALL_ONLY'
    rc = PV.main()
    if rc != 0 or not P['proj'].exists():
        return Outcome.fail('CLASSIC_RUN_PROJECTION_REFUSED', f'proj_v1 returned {rc}')
    proj = json.loads(P['proj'].read_text())
    if proj.get('market_arm') != 'FOOTBALL_ONLY':
        return Outcome.fail('CLASSIC_RUN_ARM_NOT_APPLIED',
                            f'the projection records market_arm={proj.get("market_arm")!r}')

    # 3. FOOTBALL SANITY GATE on the projection, before any draw.
    absent = [v['name'] for v in state['players'].values()
              if v['current_availability']['status'] in ('REPORTED_INACTIVE_OFFICIAL_RELEASE_CITED',
                                                          'REPORTED_INACTIVE_HIGH_CONFIDENCE',
                                                          'CONFIRMED_INACTIVE')]
    clubs = sorted({c for g in state['games'].values() for c in (g['away'], g['home'])})
    sane = FS.assess(proj, absent=absent, clubs=clubs, units=('DST',))

    # 4. JOINT DRAWS, one game at a time, merged on a single world index.
    merged, per_game, td = {}, {}, pathlib.Path(tempfile.mkdtemp(prefix='classic_draws_'))
    stats_all, game_worlds = {}, {}
    for i, (gid, g) in enumerate(sorted(state['games'].items())):
        away, home = g['away'], g['home']
        sl = {'game_id': gid, 'away': away, 'home': home, 'week': state['week'], 'season': state['season'],
              'kickoff_et_naive': state['kickoff'],
              'environment': {'games': {f'{away}@{home}': state['environment']['games'][f'{away}@{home}']}}}
        sp = td / f'{gid}.state.json'
        sp.write_text(json.dumps(sl))
        SD.OUT = td / f'{gid}.draws.json'
        o = SD.build(str(P['proj']), str(sp), n_sims=n_sims, seed=SEED + i,
                     volume_centre=sim_game.VOLUME_CENTRE_PROJECTION)
        if o.state.value != 'PASS':
            per_game[gid] = {'state': o.state.value, 'code': o.code, 'detail': o.detail}
            continue
        art = o.value
        per_game[gid] = {'state': 'PASS', 'n_players': art['n_players'], 'seed': SEED + i,
                         'scoring_centre': art['scoring_centre'], 'market_arm': art['market_arm'],
                         'identities': art['identities_verified_by_the_simulator']}
        for k, v in art['draws'].items():
            if k in merged:
                return Outcome.fail('CLASSIC_RUN_DRAW_KEY_COLLISION', f'{k} drawn in two games')
            merged[k] = v
        if tuple(art.get('STAT_FIELDS') or ()) != STAT_FIELDS or not art.get('stat_draws'):
            return Outcome.fail('CLASSIC_RUN_NO_STAT_WORLDS',
                                f'{gid}: the simulator returned no per-world stat lines in {STAT_FIELDS}')
        stats_all.update(art['stat_draws'])
        game_worlds[gid] = {'world_points': art.get('world_points'), 'club_worlds': art.get('club_worlds')}
    refused = {g: v for g, v in per_game.items() if v['state'] != 'PASS'}
    # UNCONDITIONAL dk_points: the simulator's shares are the projection's unconditional volumes,
    # so its mean is the unconditional expectation. Comparing to dk_points_if_plays would read a
    # backup quarterback's as-if-starting number as a gap.
    targets = {SD.S.player_key(r['name'], r['team']): r.get('dk_points')
               for r in proj['rows'].values() if isinstance(r.get('dk_points'), (int, float))}
    raw_gap = {}
    for k, v in merged.items():
        if k in targets and v:
            raw_gap[k] = round(sum(v) / len(v) - targets[k], 3)
    stat_worlds = None
    if player_mean_anchor == ANCHOR_EFFICIENCY:
        rows_by_key = {SD.S.player_key(r['name'], r['team']): r for r in proj['rows'].values()}
        dk_new, stat_worlds, eff = efficiency_worlds(stats_all, rows_by_key, float(proj['int_rate']), SEED + 99)
        skill = set(dk_new)
        merged = {**merged, **dk_new}
        rest = {k: v for k, v in merged.items() if k not in skill}       # DST: no stat line
        rest, dst_acc = anchor_means(rest, targets)
        merged.update(rest)
        resid = {k: round(sum(v) / len(v) - targets[k], 3) for k, v in merged.items() if k in targets and k in skill}
        anchor = {'efficiency': eff, 'dst_multiplicative': dst_acc,
                  'residual_gap_after_efficiency': resid,
                  'residual_gap_abs_max': max((abs(x) for x in resid.values()), default=None),
                  'RESIDUAL_MEANS': 'touchdown count and bonus thresholds as simulated; not rescaled'}
    elif player_mean_anchor == ANCHOR_PROJECTION:
        merged, anchor = anchor_means(merged, targets)
    elif player_mean_anchor == ANCHOR_NONE:
        anchor = {'n_anchored': 0, 'NOTE': 'draws left as simulated'}
    else:
        return Outcome.fail('CLASSIC_RUN_ANCHOR_UNKNOWN', f'{player_mean_anchor!r} is not a declared anchor')
    anchor = {'mode': player_mean_anchor, **anchor,
              'raw_gap_sim_minus_projection': raw_gap,
              'raw_gap_abs_max': max((abs(x) for x in raw_gap.values()), default=None)}
    doc = {
        'ARTIFACT': 'CLASSIC_SLATE_DRAWS', 'slate_id': slate_id, 'season': state['season'],
        'week': state['week'], 'n_sims': n_sims, 'n_players': len(merged),
        'market_arm': 'FOOTBALL_ONLY', 'volume_centre': sim_game.VOLUME_CENTRE_PROJECTION,
        'CROSS_GAME_DEPENDENCE': 'NONE: games are simulated independently and merged on one world index',
        'projection_sha256': hashlib.sha256(P['proj'].read_bytes()).hexdigest(),
        'state_sha256': hashlib.sha256(P['state'].read_bytes()).hexdigest(),
        'per_game': per_game, 'games_refused': refused,
        'player_mean_anchor': anchor,
        'football_sanity': {'state': sane.state.value, 'code': sane.code, 'detail': sane.detail,
                            'flags': (sane.evidence or {}).get('flags')},
        'draws': merged,
    }
    P['draws'].write_text(json.dumps(doc, separators=(',', ':'), default=str))
    if stat_worlds is not None:
        _write_worlds(P['worlds'], stat_worlds, game_worlds, doc['projection_sha256'])
    if refused:
        return Outcome.fail('CLASSIC_RUN_GAMES_REFUSED', f'{len(refused)} game(s) refused: {sorted(refused)}',
                            refused=refused, path=str(P['draws'].relative_to(_REPO)))
    return Outcome.measured('CLASSIC_SLATE_DRAWN', {'n_players': len(merged)}, n_measured=len(merged),
                            what='players with joint draws', detail=(
                                f'{len(merged)} players x {n_sims} worlds over {len(per_game)} games; '
                                f'sanity {sane.state.value}[{sane.code}]'),
                            sanity=sane.state.value, sanity_code=sane.code,
                            path=str(P['draws'].relative_to(_REPO)))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('slate_id')
    ap.add_argument('--n-sims', type=int, default=2000)
    ap.add_argument('--player-mean-anchor', default=ANCHOR_EFFICIENCY,
                    choices=(ANCHOR_EFFICIENCY, ANCHOR_PROJECTION, ANCHOR_NONE))
    a = ap.parse_args()
    o = run(a.slate_id, n_sims=a.n_sims, player_mean_anchor=a.player_mean_anchor)
    print(f'{o.state.value}[{o.code}] {o.detail}')
    return 0 if o.state.value == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
