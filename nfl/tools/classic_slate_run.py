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


def paths(slate_id):
    return {'state': OUT_DIR / f'DK_{slate_id}_EARLY_STATE.json',
            'proj': OUT_DIR / f'DK_{slate_id}_EARLY_PROJ.json',
            'draws': OUT_DIR / f'DK_{slate_id}_EARLY_DRAWS.json'}


def run(slate_id: str, *, n_sims: int = 2000) -> Outcome:
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
    refused = {g: v for g, v in per_game.items() if v['state'] != 'PASS'}
    doc = {
        'ARTIFACT': 'CLASSIC_SLATE_DRAWS', 'slate_id': slate_id, 'season': state['season'],
        'week': state['week'], 'n_sims': n_sims, 'n_players': len(merged),
        'market_arm': 'FOOTBALL_ONLY', 'volume_centre': sim_game.VOLUME_CENTRE_PROJECTION,
        'CROSS_GAME_DEPENDENCE': 'NONE: games are simulated independently and merged on one world index',
        'projection_sha256': hashlib.sha256(P['proj'].read_bytes()).hexdigest(),
        'state_sha256': hashlib.sha256(P['state'].read_bytes()).hexdigest(),
        'per_game': per_game, 'games_refused': refused,
        'football_sanity': {'state': sane.state.value, 'code': sane.code, 'detail': sane.detail,
                            'flags': (sane.evidence or {}).get('flags')},
        'draws': merged,
    }
    P['draws'].write_text(json.dumps(doc, separators=(',', ':'), default=str))
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
    a = ap.parse_args()
    o = run(a.slate_id, n_sims=a.n_sims)
    print(f'{o.state.value}[{o.code}] {o.detail}')
    return 0 if o.state.value == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
