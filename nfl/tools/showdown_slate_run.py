#!/usr/bin/env python3.12
"""One Showdown game, end to end through the football layers, in Sunday's accepted configuration.

    python3.12 nfl/tools/showdown_slate_run.py ATL_NO_2026W4 [--n-sims 2000]

The steps are `classic_slate_run.run`'s, for one game and one set of paths, so tonight's showdown is
built by the same football as Sunday's classic slate rather than by an older showdown default:

  role state -> proj_v1 (MARKET_ARM = FOOTBALL_ONLY) -> football sanity gate
  -> showdown_draws.build(volume_centre = projection, n_calib = n_sims) -> efficiency worlds

TWO DIFFERENCES FROM THE CLASSIC RUN, both declared:
  KICKERS are scored inside the simulated worlds (nfl/tools/kicker_world.py) and are NOT rescaled to
  kicker_model's point projection. The classic run never rosters a kicker; its anchor step would
  have pulled a same-world distribution onto a number computed with a -1 missed-FG rule the draws
  do not use (see kicker_world.MISS_RULE). The kicker's projection IS his draw mean.
  CPT is never drawn separately: a captain's score is the same world's FLEX score x 1.5, applied by
  the candidate scorer (nfl/dfs/showdown/candidates.py), so there is one distribution per person.

DST keeps the classic run's multiplicative step onto its projection (it has no stat line here).
Fits nothing, fetches nothing, never reads FantasyCruncher or a sportsbook price.
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
from nfl.tools import classic_slate_run as CR  # noqa: E402

SEED = 20261005


def paths(tag, work=None):
    """Where a slate's intermediates live. With `work` (a scenario directory) EVERY intermediate -- state,
    projection, role state, DST rates, draws, worlds -- is written there and nowhere shared, so two scenarios
    cannot read each other's files (TB@DAL 2026-10-08). Without it, the legacy per-tag paths."""
    d = _REPO / 'nfl/dfs/salaries' / f'showdown_{tag.split("_2026")[0].lower()}'
    w = pathlib.Path(work) if work is not None else d
    return {'dir': d, 'work': w, 'state': w / f'SHOWDOWN_{tag}_STATE.json', 'proj': w / f'SHOWDOWN_{tag}_PROJ.json',
            'draws': w / f'SHOWDOWN_{tag}_DRAWS.json', 'worlds': w / f'SHOWDOWN_{tag}_WORLDS.npz',
            'role': (w / 'ROLE_STATE.json') if work is not None else None,
            'dst_rates': (w / 'DST_RATES.json') if work is not None else None}


def run(tag, *, n_sims=2000, seed=SEED, work=None) -> Outcome:
    from nfl.tools import proj_v1 as PV, role_state as RS, showdown_draws as SD, football_sanity as FS
    from nfl.tools import availability as AV, dst_model
    from nfl.sim import game as sim_game
    P = paths(tag, work)
    if work is not None:
        # the role state and the DST rates are otherwise written to fixed nfl/derived/ paths shared by every run
        RS.OUT = PV.ROLE = P['role']
        dst_model.OUT = P['dst_rates']
    if not P['state'].exists():
        return Outcome.blocked('SHOWDOWN_RUN_NO_STATE', f'{P["state"]} not built', cause=Cause.DATA)
    state = json.loads(P['state'].read_text())

    RS.POST = P['state']
    rs = RS.run()
    if rs.state.value != 'PASS':
        return rs
    PV.POST, PV.OUT, PV.SLATE_WEEK = P['state'], P['proj'], int(state['week'])
    PV.MARKET_ARM = 'FOOTBALL_ONLY'
    rc = PV.main()
    if rc != 0 or not P['proj'].exists():
        return Outcome.fail('SHOWDOWN_RUN_PROJECTION_REFUSED', f'proj_v1 returned {rc}')
    proj = json.loads(P['proj'].read_text())
    if proj.get('market_arm') != 'FOOTBALL_ONLY':
        return Outcome.fail('SHOWDOWN_RUN_ARM_NOT_APPLIED', f'market_arm={proj.get("market_arm")!r}')

    absent = [v['name'] for v in state['players'].values()
              if v['current_availability']['status'] in AV.ABSENT_STATUSES]
    sane = FS.assess(proj, absent=absent, clubs=[state['away'], state['home']], units=('DST',))

    td = pathlib.Path(tempfile.mkdtemp(prefix='showdown_draws_'))
    SD.OUT = td / 'draws.json'
    o = SD.build(str(P['proj']), str(P['state']), n_sims=n_sims, seed=seed,
                 volume_centre=sim_game.VOLUME_CENTRE_PROJECTION, n_calib=n_sims)
    if o.state.value != 'PASS':
        return o
    art = o.value
    draws = {k: list(v) for k, v in art['draws'].items()}
    if tuple(art.get('STAT_FIELDS') or ()) != CR.STAT_FIELDS or not art.get('stat_draws'):
        return Outcome.fail('SHOWDOWN_RUN_NO_STAT_WORLDS', 'the simulator returned no per-world stat lines')

    rows_by_key = {SD.S.player_key(r['name'], r['team']): r for r in proj['rows'].values()}
    targets = {k: r.get('dk_points') for k, r in rows_by_key.items()
               if isinstance(r.get('dk_points'), (int, float))}
    raw_gap = {k: round(sum(v) / len(v) - targets[k], 3) for k, v in draws.items() if k in targets and v}
    kickers = {k for k, r in rows_by_key.items() if r.get('position') == 'K'}
    dk_new, stat_worlds, eff = CR.efficiency_worlds(art['stat_draws'], rows_by_key,
                                                    float(proj['int_rate']), seed + 99)
    skill = set(dk_new)
    draws.update(dk_new)
    dst = {k: v for k, v in draws.items() if k not in skill and k not in kickers}
    dst, dst_acc = CR.anchor_means(dst, targets)
    draws.update(dst)
    resid = {k: round(sum(v) / len(v) - targets[k], 3) for k, v in draws.items() if k in targets and k in skill}
    n = {len(v) for v in draws.values()}
    if n != {n_sims}:
        return Outcome.fail('SHOWDOWN_RUN_RAGGED', f'draw lengths {sorted(n)}')
    doc = {
        'ARTIFACT': 'SHOWDOWN_SLATE_DRAWS', 'tag': tag, 'game_id': state['game_id'],
        'away': state['away'], 'home': state['home'], 'kickoff_et_naive': state['kickoff_et_naive'],
        'season': state['season'], 'week': state['week'], 'n_sims': n_sims, 'seed': seed,
        'n_players': len(draws), 'market_arm': 'FOOTBALL_ONLY',
        'volume_centre': sim_game.VOLUME_CENTRE_PROJECTION,
        'scoring_centre': art['scoring_centre'],
        'identities_verified_by_the_simulator': art['identities_verified_by_the_simulator'],
        'projection_sha256': hashlib.sha256(P['proj'].read_bytes()).hexdigest(),
        'state_sha256': hashlib.sha256(P['state'].read_bytes()).hexdigest(),
        'kickers': art['kickers'],
        'player_mean_anchor': {'mode': CR.ANCHOR_EFFICIENCY, 'efficiency': eff, 'dst_multiplicative': dst_acc,
                               'kickers': 'LEFT AS DRAWN IN THE WORLD (not anchored)',
                               'residual_gap_after_efficiency': resid,
                               'raw_gap_sim_minus_projection': raw_gap},
        'football_sanity': {'state': sane.state.value, 'code': sane.code, 'detail': sane.detail,
                            'flags': (sane.evidence or {}).get('flags')},
        'world_points': art.get('world_points'), 'club_scoring_worlds': art.get('club_scoring_worlds'),
        'dst_components': art.get('dst_components'),
        'club_worlds': art.get('club_worlds'),
        'CLUB_WORLDS_MEANING': '(pass attempts, rush attempts, targets, throwaways) per club per world',
        'DST_COMPONENTS_MEANING': '(sacks, takeaways, defensive TDs, safeties) per world, before the DST anchor step',
        # per-world stat lines after the efficiency step (interceptions included), keyed like draws
        'qb_interceptions': {k: [w[10] for w in v] for k, v in stat_worlds.items()
                             if rows_by_key.get(k, {}).get('position') == 'QB'},
        'CPT_RULE': 'CPT score = FLEX score in the same world x 1.5; one distribution per person',
        'draws': draws,
    }
    P['draws'].write_text(json.dumps(doc, separators=(',', ':'), default=str))
    CR._write_worlds(P['worlds'], stat_worlds,
                     {state['game_id']: {'world_points': art['world_points']}}, doc['projection_sha256'])
    return Outcome.ok('SHOWDOWN_SLATE_DRAWN', {'path': str(P['draws'].relative_to(_REPO))},
                      f'{len(draws)} players x {n_sims} worlds; sanity {sane.state.value}[{sane.code}]',
                      sanity=sane.state.value)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('tag')
    ap.add_argument('--n-sims', type=int, default=2000)
    a = ap.parse_args()
    o = run(a.tag, n_sims=a.n_sims)
    print(o.state.value, o.code, o.detail)
    return 0 if o.state.value == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
