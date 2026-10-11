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
import collections
import hashlib
import json
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

def _out_dir():
    import importlib.util as _u
    _s = _u.spec_from_file_location('classic_paths', _REPO / 'nfl/tools/classic_paths.py')
    _m = _u.module_from_spec(_s)
    _s.loader.exec_module(_m)
    return _m.out_dir()


#: nfl/dfs/salaries, or a declared arm's folder under nfl/dfs/salaries/arms/ (NFL_CLASSIC_OUT_DIR; classic_paths.py)
OUT_DIR = _out_dir()
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


#: The declared corrected arm (owner decision E2: it runs beside the incumbent, the owner chooses). Selected by
#: NFL_CLASSIC_ARM=CORRECTED_V1 with NFL_CLASSIC_OUT_DIR under nfl/dfs/salaries/arms/ (classic_paths.py).
ARM_INCUMBENT = 'INCUMBENT'
ARM_CORRECTED = 'CORRECTED_V1'
#: the CORRECTED_V1 arm's world builder: ECW-3 (nfl/research/accounting_repair/PREREG_ECW3.md)
ECW_VERSION = 3


def participation_inputs(state: dict, proj: dict, P: dict, n_sims: int, seed: int):
    """(by_club, account) for the CORRECTED_V1 arm: each designated player's per-world phi and the club shares the
    projection engine gives when he is absent.

    VARIANTS, NOT ONE PER PLAYER. Clubs are allocated independently, so variant j removes the j-th designated player
    of EVERY club at once; max(designated per club) projection re-runs give every player his own absent pattern. Each
    variant is role_state -> proj_v1 on a temporary copy of the state, written to a temporary directory."""
    import copy
    import random as _r
    from nfl.sim import participation as PART
    from nfl.tools import availability as AV, proj_v1 as PV, role_state as RS, showdown_draws as SD
    tables = PART.load()
    rows = proj['rows']
    designated = collections.defaultdict(list)
    for dk, pl in state['players'].items():
        if pl['current_availability']['status'] in AV.ABSENT_STATUSES:
            continue
        r = rows.get(dk) or {}
        if r.get('projection_state') not in ('PROJECTED', 'PROJECTED_COLD_START'):
            continue
        u = PART.classify(pl, r)
        if u is not None:
            designated[pl['team']].append((dk, u))
    n_slots = max((len(v) for v in designated.values()), default=0)
    # the variants are kept beside the arm's other artifacts, so the release record and the tests can hash them
    td = P['state'].parent / f"{P['state'].name.replace('_STATE.json', '')}_PARTICIPATION_VARIANTS"
    td.mkdir(parents=True, exist_ok=True)
    saved = (RS.POST, RS.OUT, PV.POST, PV.OUT, PV.ROLE)
    variant_rows = []
    try:
        for j in range(n_slots):
            st = copy.deepcopy(state)
            for club, lst in designated.items():
                if j < len(lst):
                    st['players'][lst[j][0]]['current_availability']['status'] = AV.PARTICIPATION_VARIANT_ABSENT
            sp, rp, pp = td / f'V{j}_STATE.json', td / f'V{j}_ROLE.json', td / f'V{j}_PROJ.json'
            sp.write_text(json.dumps(st))
            RS.POST, RS.OUT = sp, rp
            o = RS.run()
            if o.state.value != 'PASS':
                raise RuntimeError(f'variant {j} role state: {o.code} {o.detail}')
            PV.POST, PV.OUT, PV.ROLE = sp, pp, rp
            if PV.main() != 0:
                raise RuntimeError(f'variant {j} projection refused')
            variant_rows.append(json.loads(pp.read_text())['rows'])
    finally:
        RS.POST, RS.OUT, PV.POST, PV.OUT, PV.ROLE = saved
    by_club, account = {}, {}
    for club, lst in designated.items():
        for j, (dk, u) in enumerate(lst):
            sp = PART.spec(u, tables)
            rng = _r.Random(f'{seed}|participation|{dk}')
            phi = PART.draw_phi(sp, n_sims, rng)
            key = SD.S.player_key(state['players'][dk]['name'], club)
            absent = SD._shares(list(variant_rows[j].values()), club)
            by_club.setdefault(club, {})[key] = {'phi': phi, 'absent_shares': absent}
            srt = sorted(phi)
            account[key] = {'dk_id': dk, 'variant': j, 'unit': u, 'p_no_participation': sp['p_no_participation'],
                            'p_no_participation_basis': sp['p_no_participation_basis'], 'phi_basis': sp['phi_basis'],
                            'worlds_phi_zero': sum(1 for x in phi if x <= 0), 'phi_mean': round(sum(phi) / n_sims, 4),
                            'phi_p10_p50_p90': [round(srt[int(q * (n_sims - 1))], 4) for q in (0.1, 0.5, 0.9)],
                            'LIMITATIONS': sp['LIMITATIONS']}
    variants = {f'V{j}': {'removed': {c: lst[j][0] for c, lst in designated.items() if j < len(lst)},
                          'proj_sha256': hashlib.sha256((td / f'V{j}_PROJ.json').read_bytes()).hexdigest(),
                          'path': str((td / f'V{j}_PROJ.json').relative_to(_REPO))} for j in range(n_slots)}
    return by_club, {'n_variants': n_slots, 'variants': variants, 'designated': account,
                     'SOURCES': {'p_no_participation': 'PM1_TABLE.json', 'phi': 'PM3_PHI.json',
                                 'pass_rate': 'REDISTRIBUTION_STUDY.json (association, leaders only)'}}


def qb_volume_inputs(slate_id: str, state: dict, proj: dict):
    """({club: {'pass_attempts': delta}}, account): the registered QBCTX-DB1 dropbacks deviation for each club's
    starter, when the slate declares a forecast file (early_only 'qbctx_db1_forecasts').

    A forecast is used only when its starter is the state's rank-1 quarterback for that club (by GSIS id); otherwise
    the club gets no delta and the reason is recorded. QBCTX-DB1 is registered and prospective only (its verdict is
    NOT_YET_EVALUABLE until 40 QB-change games are graded); using it here is the CORRECTED_V1 arm, beside the
    incumbent, never production."""
    from nfl.dfs.salaries import early_only as EO
    f = EO.slate_files(slate_id).get('qbctx_db1_forecasts')
    if not f:
        return {}, {'state': 'NOT_DECLARED', 'why': 'the slate declares no QBCTX-DB1 forecast file'}
    fp = _REPO / f
    doc = json.loads(fp.read_text())
    starters = {}
    for v in state['players'].values():
        if v.get('position') == 'QB' and v.get('depth_rank') == 1:
            starters[v['team']] = v.get('gsis_id')
    out, acct = {}, {}
    for club, row in (doc.get('clubs') or {}).items():
        tv = (proj.get('team_volume') or {}).get(club) or {}
        dev = ((row.get('qb_deviation') or {}).get('dropbacks') or {}).get('delta_applied')
        if starters.get(club) != row.get('starter_gsis_id'):
            acct[club] = {'applied': False, 'why': f"forecast starter {row.get('starter_gsis_id')} is not the state's "
                                                   f"rank-1 QB {starters.get(club)}"}
            continue
        if dev is None or not tv.get('proj_dropbacks'):
            acct[club] = {'applied': False, 'why': 'no dropbacks deviation or no projected dropbacks'}
            continue
        d = float(dev) * float(tv['proj_pass_attempts']) / float(tv['proj_dropbacks'])
        out[club] = {'pass_attempts': d}
        acct[club] = {'applied': True, 'starter': row.get('starter'), 'subset': row.get('subset'),
                      'dropbacks_delta': round(float(dev), 4), 'pass_attempts_delta': round(d, 4)}
    return out, {'state': 'APPLIED', 'source': f, 'source_sha256': hashlib.sha256(fp.read_bytes()).hexdigest(),
                 'cutoff': doc.get('cutoff'), 'clubs': acct}


def run(slate_id: str, *, n_sims: int = 2000, player_mean_anchor: str = ANCHOR_EFFICIENCY, arm: str = None) -> Outcome:
    from nfl.tools import proj_v1 as PV, role_state as RS, showdown_draws as SD, football_sanity as FS
    from nfl.tools import availability as AV
    from nfl.sim import game as sim_game
    import os as _os
    arm = arm or _os.environ.get('NFL_CLASSIC_ARM') or ARM_INCUMBENT
    if arm not in (ARM_INCUMBENT, ARM_CORRECTED):
        return Outcome.fail('CLASSIC_RUN_ARM_UNKNOWN', f'{arm!r} is not a declared arm')
    if arm == ARM_CORRECTED and OUT_DIR == _REPO / 'nfl/dfs/salaries':
        return Outcome.fail('CLASSIC_RUN_CORRECTED_ARM_IN_PRODUCTION_DIR',
                            'the corrected arm runs beside the incumbent, in its own folder (NFL_CLASSIC_OUT_DIR under '
                            'nfl/dfs/salaries/arms/); it never writes the production files')
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
              if v['current_availability']['status'] in AV.ABSENT_STATUSES]
    clubs = sorted({c for g in state['games'].values() for c in (g['away'], g['home'])})
    sane = FS.assess(proj, absent=absent, clubs=clubs, units=('DST',))

    part_by_club, part_account = {}, None
    # NFL_CLASSIC_PARTICIPATION_CONTROL=1: the corrected arm WITHOUT participation, a declared control used only to
    # isolate what participation itself changes (integration tests, owner comparisons). Recorded in the artifact.
    control = _os.environ.get('NFL_CLASSIC_PARTICIPATION_CONTROL') == '1'
    if arm == ARM_CORRECTED and control:
        part_account = {'CONTROL': 'participation disabled by NFL_CLASSIC_PARTICIPATION_CONTROL=1'}
    elif arm == ARM_CORRECTED:
        try:
            part_by_club, part_account = participation_inputs(state, proj, P, n_sims, SEED)
        except (RuntimeError, OSError, ValueError, KeyError) as e:
            return Outcome.fail('CLASSIC_RUN_PARTICIPATION_REFUSED', f'{type(e).__name__}: {e}')

    qb_delta, qb_account = ({}, None)
    if arm == ARM_CORRECTED:
        qb_delta, qb_account = qb_volume_inputs(slate_id, state, proj)

    # 4. JOINT DRAWS, one game at a time, merged on a single world index.
    merged, per_game, td = {}, {}, pathlib.Path(tempfile.mkdtemp(prefix='classic_draws_'))
    stats_all, game_worlds, coherent_worlds = {}, {}, {}
    for i, (gid, g) in enumerate(sorted(state['games'].items())):
        away, home = g['away'], g['home']
        sl = {'game_id': gid, 'away': away, 'home': home, 'week': state['week'], 'season': state['season'],
              'kickoff_et_naive': state['kickoff'],
              'environment': {'games': {f'{away}@{home}': state['environment']['games'][f'{away}@{home}']}}}
        sp = td / f'{gid}.state.json'
        sp.write_text(json.dumps(sl))
        SD.OUT = td / f'{gid}.draws.json'
        # CALIBRATE ON THE FULL DRAW COUNT. The default calibrates on 1,000 worlds and then judges the
        # final 2,000 against the final's own SE only, so calibration noise can push a club just
        # outside 3 SE: measured 2026W4 GB@TB, GB rush attempts gap 0.92 vs tolerance 0.87 at 1,000;
        # -0.03 at 2,000. Precision is raised; the reconciliation gate is unchanged.
        o = SD.build(str(P['proj']), str(sp), n_sims=n_sims, seed=SEED + i,
                     volume_centre=sim_game.VOLUME_CENTRE_PROJECTION, n_calib=n_sims,
                     participation={c: part_by_club[c] for c in (away, home) if c in part_by_club} or None,
                     volume_delta={c: qb_delta[c] for c in (away, home) if c in qb_delta} or None)
        if o.state.value != 'PASS':
            per_game[gid] = {'state': o.state.value, 'code': o.code, 'detail': o.detail}
            continue
        art = o.value
        if arm == ARM_CORRECTED:
            # BOX-SCORE-COHERENT WORLDS (task #45 P1-5): receiving yards are caught yards, QB passing yards are the sum
            # of his receivers' yards, every TD sits on a catch or a carry, INTs are opposing takeaways, club points are
            # event sums (nfl/sim/event_consistent_worlds.py). Replaces efficiency_worlds for this arm only.
            from nfl.sim import event_consistent_worlds as ECW
            rows_by_key_g = {SD.S.player_key(r['name'], r['team']): r for r in proj['rows'].values()}
            eo = ECW.build(art, rows_by_key_g, float(proj['int_rate']), SEED + i, incumbent_seed=SEED + 99, version=ECW_VERSION)
            if eo.state.value != 'PASS':
                per_game[gid] = {'state': eo.state.value, 'code': eo.code, 'detail': eo.detail}
                continue
            ev = eo.value
            art = {**art, 'draws': ev['draws'], 'stat_draws': None, 'world_points': ev['world_points'],
                   '_coherent_stat_worlds': ev['stat_worlds'], '_coherent_account': ev['account']}
        per_game[gid] = {'state': 'PASS', 'n_players': art['n_players'], 'seed': SEED + i,
                         'scoring_centre': art['scoring_centre'], 'market_arm': art['market_arm'],
                         'identities': art['identities_verified_by_the_simulator']}
        for k, v in art['draws'].items():
            if k in merged:
                return Outcome.fail('CLASSIC_RUN_DRAW_KEY_COLLISION', f'{k} drawn in two games')
            merged[k] = v
        if arm == ARM_CORRECTED:
            coherent_worlds.update(art['_coherent_stat_worlds'])
            per_game[gid]['coherent_account'] = {c: {k: v for k, v in a.items() if not isinstance(v, (list, dict))}
                                                 for c, a in (art['_coherent_account'].get('clubs') or {}).items()}
            per_game[gid]['participation'] = art.get('participation_account')
        elif tuple(art.get('STAT_FIELDS') or ()) != STAT_FIELDS or not art.get('stat_draws'):
            return Outcome.fail('CLASSIC_RUN_NO_STAT_WORLDS',
                                f'{gid}: the simulator returned no per-world stat lines in {STAT_FIELDS}')
        else:
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
    if arm == ARM_CORRECTED:
        # the coherent worlds ARE the published worlds; no per-player rescale is applied after them (a rescale is what
        # broke passing = receiving yards in the incumbent)
        stat_worlds = coherent_worlds
        resid = {k: round(sum(v) / len(v) - targets[k], 3) for k, v in merged.items() if k in targets and v}
        anchor = {'mode': 'EVENT_CONSISTENT_NO_RESCALE', 'residual_gap_vs_projection': resid,
                  'residual_gap_abs_max': max((abs(x) for x in resid.values()), default=None),
                  'raw_gap_sim_minus_projection': raw_gap}
    elif player_mean_anchor == ANCHOR_EFFICIENCY:
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
    if arm != ARM_CORRECTED:
        anchor = {'mode': player_mean_anchor, **anchor,
                  'raw_gap_sim_minus_projection': raw_gap,
                  'raw_gap_abs_max': max((abs(x) for x in raw_gap.values()), default=None)}
    doc = {
        'ARTIFACT': 'CLASSIC_SLATE_DRAWS', 'slate_id': slate_id, 'season': state['season'], 'arm': arm,
        'participation': part_account, 'qb_conditioned_volume': qb_account,
        'run_id': __import__('os').environ.get('NFL_CLASSIC_RUN_ID'),   # None when run by hand (task #45)
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
