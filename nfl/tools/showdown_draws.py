#!/usr/bin/env python3.12
"""Genuine simulation draws for one showdown game, from the joint game simulator.

WHY THIS EXISTS. `near_optimal_candidates` needs a DISTRIBUTION per player, not a mean, because
p_optimal is a statement about the joint behaviour of six players under a salary cap. The runner
refuses `SHOWDOWN_DRAWS_ABSENT` rather than manufacture one, so this is the module that produces them.

NOTHING HERE INVENTS A DISTRIBUTION. The draws come from `nfl/sim/game.py:simulate_game`, which draws
the game total and margin from measured residuals, converts them to club volume through the measured
volume response, and allocates every club total multinomially across players so the identities hold
EXACTLY -- player targets sum to club pass attempts, player TDs sum to club offensive TDs, home points
plus away points equal the drawn total, and four more. `simulate_game` verifies all seven on every
simulated game and FAILS on any violation.

THE SHARES ARE THE PROJECTION'S OWN OUTPUT, not a second model. Each player's target, carry and pass
attempt shares are his projected conditional volume over his club's total, and his TD shares are the
model's own expected receiving and rushing touchdowns over the club's. That last point is a small
improvement on the precedent in `validate_correlations.py`, which declares using opportunity share as
a proxy for TD share because its replay has no TD table; here the TD expectations exist, so they are
used directly.

KICKERS ARE NOT SIMULATED BY THE GAME SIMULATOR and are not left out either. `simulate_game` has no
kicker pathway, and dropping kickers would delete a sixth of a showdown roster. Their draws are
generated from `kicker_model`'s own measured components -- attempts per game by distance band and the
league make rate for that band -- as Poisson attempts and binomial makes. That is a generative model
over measured rates, not a mean dressed up as a distribution, and the bands and rates are the same
ones the point projection uses, so the draw mean reconciles with it.

ABSENT PLAYERS GET NO DRAWS. A player ruled out has no distribution, not a distribution centred on
zero, and he is excluded from the club's share denominators so the remaining players' shares still sum
to one -- which is what redistributing his opportunity means.
"""
from __future__ import annotations

import collections
import json
import pathlib
import random
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.sim import game as sim_game  # noqa: E402
from nfl.sim import share_model as share_mod  # noqa: E402
from nfl.tools import kicker_model, showdown_to_portfolio as S  # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

OUT = _REPO / 'nfl/dfs/salaries/SHOWDOWN_TONIGHT_DRAWS.json'

#: Draws per player. The optimiser solves one exact dynamic program PER WORLD, so this is the main
#: cost driver. 2000 is the simulator's own default.
N_SIMS = 2000

#: Fixed and recorded. A draw set whose numbers move between runs cannot be compared with itself.
SEED = 20261001

#: Positional catch rates, used only when a player has no projected targets to derive one from. Same
#: fallback the correlation validator uses.
CATCH_RATE = {'WR': 0.63, 'TE': 0.70, 'RB': 0.75}


def _shares(rows, club):
    """Each club's players with their shares of the club's own projected volume."""
    mem = [r for r in rows if r.get('team') == club
           and isinstance(r.get('dk_points'), (int, float))
           and r.get('position') in ('QB', 'RB', 'WR', 'TE')]
    tot = collections.Counter()
    for r in mem:
        tot['targets'] += float(r.get('targets') or 0.0)
        tot['carries'] += float(r.get('carries') or 0.0)
        tot['pass_attempts'] += float(r.get('pass_attempts') or 0.0)
        td = r.get('td') or {}
        tot['rec_td'] += float(td.get('rec_td') or 0.0)
        tot['rush_td'] += float(td.get('rush_td') or 0.0)
    # Depth order within club and position, for the slot label the share model keys its
    # concentration on. Derived from the projection's own volumes, not from a separate chart.
    order = collections.defaultdict(list)
    for r in mem:
        pos = r['position']
        key = float(r.get('carries') or 0.0) if pos == 'RB' else float(r.get('targets') or 0.0)
        order[pos].append((-key, r['name']))
    rank = {}
    for pos, lst in order.items():
        for i, (_k, nm) in enumerate(sorted(lst), start=1):
            rank[(pos, nm)] = i

    def share(v, key):
        t = tot[key]
        return (float(v or 0.0) / t) if t > 0 else 0.0

    out = []
    for r in mem:
        pos, nm = r['position'], r['name']
        td = r.get('td') or {}
        tg, rc = float(r.get('targets') or 0.0), float(r.get('receptions') or 0.0)
        k = rank.get((pos, nm))
        slot = f'{pos}{k}' if k and f'{pos}{k}' in (share_mod.TARGET_SLOTS
                                                    + share_mod.CARRY_SLOTS) else 'OTHER'
        out.append({
            'id': S.player_key(nm, club), 'position': pos,
            'target_share': share(r.get('targets'), 'targets') if pos in ('WR', 'TE', 'RB') else 0.0,
            # EVERY skill position carries what the projection allocated it. This was gated to RB,
            # so a quarterback's (and a receiver's gadget) carries never reached the joint worlds and
            # the club's rush attempts were reallocated to backs: Watson drew 0.0 carries against a
            # 6.17 projection, Judkins 13.9 DK against 10.4. tot['carries'] already sums all four.
            'carry_share': share(r.get('carries'), 'carries') if pos in ('QB', 'RB', 'WR', 'TE') else 0.0,
            'pass_att_share': share(r.get('pass_attempts'), 'pass_attempts') if pos == 'QB' else 0.0,
            'pass_td_share': share(td.get('rec_td'), 'rec_td') if pos in ('WR', 'TE', 'RB') else 0.0,
            'rush_td_share': share(td.get('rush_td'), 'rush_td') if pos in ('RB', 'QB') else 0.0,
            'catch_rate': (rc / tg) if tg > 0 else CATCH_RATE.get(pos, 0.65),
            'slot': slot,
        })
    return out


def kicker_draws(club, n_sims, rng) -> Outcome:
    """Draws for one club's kicker, from the SAME measured bands the point projection uses."""
    m = kicker_model.measure()
    m = m.value if hasattr(m, 'value') else m
    proj = kicker_model.project(club, m)
    if proj.get('dk_points') is None:
        return Outcome.blocked('SHOWDOWN_KICKER_NOT_PROJECTABLE',
                               f'{club} has no measured kicking history', cause=Cause.DATA, club=club)
    items = proj['items']
    pts_for = {'fg_0_39': 3.0, 'fg_40_49': 4.0, 'fg_50_plus': 5.0}
    draws = []
    for _ in range(n_sims):
        tot = 0.0
        for band, pv in pts_for.items():
            it = items.get(band) or {}
            lam, mr = float(it.get('attempts') or 0.0), float(it.get('make_rate') or 0.0)
            # Poisson attempts at the measured per-game rate, then binomial makes at the measured
            # band make rate. Both parameters are measured; neither is chosen here.
            att = 0
            if lam > 0:
                L, p, k = pow(2.718281828459045, -lam), 1.0, 0
                while True:
                    p *= rng.random()
                    if p <= L:
                        break
                    k += 1
                att = k
            tot += sum(pv for _ in range(att) if rng.random() < mr)
        pat = items.get('pat') or {}
        lam = float(pat.get('attempts') or 0.0)
        att = 0
        if lam > 0:
            L, p, k = pow(2.718281828459045, -lam), 1.0, 0
            while True:
                p *= rng.random()
                if p <= L:
                    break
                k += 1
            att = k
        tot += sum(1.0 for _ in range(att) if rng.random() < 0.96)
        draws.append(tot)
    return Outcome.ok('SHOWDOWN_KICKER_DRAWN', draws, f'{club} kicker, {n_sims} draws',
                      mean=round(sum(draws) / len(draws), 3),
                      point_projection=proj['dk_points'],
                      PAT_MAKE_RATE_NOTE='0.96 is the long-run league PAT rate carried in the model')


def build(proj_path, state_path, *, n_sims: int = N_SIMS, seed: int = SEED) -> Outcome:
    proj = json.loads(pathlib.Path(proj_path).read_text())
    state = json.loads(pathlib.Path(state_path).read_text())
    rows = list(proj['rows'].values())
    away, home = state['away'], state['home']
    envs = state['environment']['games']
    env = envs.get(f'{away}@{home}') or next(iter(envs.values()))

    mo = sim_game.Model.load()
    if hasattr(mo, 'state') and mo.state.value != 'PASS':
        return mo
    model = mo.value if hasattr(mo, 'value') else mo

    spec = {'total_line': env['total_line'], 'home_spread': env['home_spread'], 'clubs': []}
    for club in (home, away):
        players = _shares(rows, club)
        if not any(p['position'] == 'QB' for p in players):
            return Outcome.fail(
                'SHOWDOWN_CLUB_HAS_NO_QUARTERBACK',
                f'{club} has no projected quarterback, so its passing volume cannot be allocated. '
                f'Every inactive quarterback was removed and none remains.', club=club)
        dst = next((r for r in rows if r.get('team') == club and r.get('position') == 'DST'
                    and isinstance(r.get('dk_points'), (int, float))), None)
        spec['clubs'].append({
            'club': club, 'players': players,
            'dst_id': (S.player_key(dst['name'], club) if dst else None),
        })

    o = sim_game.simulate_game(model, spec, n_sims=n_sims, seed=seed, retain_stats=True)
    if o.state.value != 'PASS':
        return o
    draws = {k: list(v) for k, v in o.value['draws'].items()}

    rng = random.Random(seed)
    kickers = {}
    for club in (home, away):
        k = next((r for r in rows if r.get('team') == club and r.get('position') == 'K'
                  and isinstance(r.get('dk_points'), (int, float))), None)
        if k is None:
            continue
        kd = kicker_draws(club, n_sims, rng)
        if kd.state.value != 'PASS':
            return kd
        key = S.player_key(k['name'], club)
        draws[key] = kd.value
        kickers[key] = {'mean': kd.evidence['mean'], 'point_projection': kd.evidence['point_projection']}

    lens = {len(v) for v in draws.values()}
    if len(lens) != 1:
        return Outcome.fail('SHOWDOWN_DRAWS_RAGGED_AT_BUILD',
                            f'draw lengths differ: {sorted(lens)[:4]}', lengths=sorted(lens)[:6])

    art = {
        'ARTIFACT': 'SHOWDOWN_TONIGHT_DRAWS',
        'game_id': state['game_id'], 'away': away, 'home': home,
        'kickoff_et_naive': state['kickoff_et_naive'],
        'n_sims': n_sims, 'seed': seed, 'n_players': len(draws),
        'source': 'nfl/sim/game.py simulate_game, plus kicker_model bands for the two kickers',
        # Outcome.ok puts the payload on `.value`; `.evidence` is a separate kwargs dict and
        # the key is `club_checks`, not `identities`. Reading `o.evidence.get('identities')`
        # recorded None on every run, so this artifact asserted nothing about the identities
        # while looking like it had checked them -- the project's named defect class, an empty
        # read accepted as success. The simulator does verify: a broken identity raises
        # GAME_IDENTITY_VIOLATED in nfl/sim/game.py and never reaches here.
        'identities_verified_by_the_simulator': {
            'club_checks': (o.value or {}).get('club_checks'),
            'IDENTITIES_HELD': (o.value or {}).get('IDENTITIES_HELD'),
            'allocation_mode': (o.value or {}).get('allocation_mode'),
            'share_family': (o.value or {}).get('share_family'),
        },
        'simulator_detail': o.detail or o.code,
        'kickers': kickers,
        'NOT_SYNTHESISED': ('no draw is derived from a projected mean. Player draws come from the '
                            'joint simulator and kicker draws from measured attempt and make rates.'),
        'draws': draws,
    }
    # PER-STAT WORLDS GO IN A NUMPY SIDECAR, NOT THE JSON. 2,000 worlds x 45 players x 10 stats
    # is ~11 MB as text and ~2 MB compressed; the JSON stays the small, diffable object it is and
    # the sidecar is named and hashed from it so the two cannot drift apart unnoticed.
    import hashlib
    import numpy as np
    sd = o.value.get('stat_draws') or {}
    side = OUT.with_name(OUT.stem + '_STATS.npz')
    if sd:
        np.savez_compressed(side, **{k: np.asarray(v, dtype=np.float64) for k, v in sd.items()})
        art['stat_draws_sidecar'] = {
            'path': S._rel(side), 'sha256': hashlib.sha256(side.read_bytes()).hexdigest(),
            'STAT_FIELDS': list(o.value.get('STAT_FIELDS') or ()),
            'STATS_NOT_DRAWN': list(o.value.get('STATS_NOT_DRAWN') or ()),
            'n_players': len(sd), 'keyed_by': 'name|club, same keys as draws'}
    OUT.write_text(json.dumps(art, separators=(',', ':'), default=str))
    means = {k: round(sum(v) / len(v), 3) for k, v in draws.items()}
    return Outcome.ok('SHOWDOWN_DRAWS_BUILT', art, f'{len(draws)} players, {n_sims} draws each',
                      path=S._rel(OUT), n_players=len(draws), n_sims=n_sims, seed=seed,
                      simulator=o.detail,
                      top_means=dict(sorted(means.items(), key=lambda kv: -kv[1])[:10]))


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--projections', default='nfl/dfs/salaries/SHOWDOWN_TONIGHT_PROJ.json')
    ap.add_argument('--state', default='nfl/dfs/salaries/SHOWDOWN_TONIGHT_STATE.json')
    ap.add_argument('--n-sims', type=int, default=N_SIMS)
    ap.add_argument('--seal', action='store_true',
                    help='after building, seal projection + draws into the Showdown family lane '
                         '(nfl/research/showdown_live) with a LIVE clock; refused if kickoff has passed')
    ap.add_argument('--export', default='nfl/dfs/salaries/raw/DKEntries_PIT_CLE_SHOWDOWN_2026W4.csv')
    ap.add_argument('--inactives', default='nfl/dfs/salaries/raw/OFFICIAL_INACTIVES_PIT_CLE_2026W4.json')
    ap.add_argument('--model-configuration', default='PROJ_V1_JOINT')
    a = ap.parse_args()
    o = build(a.projections, a.state, n_sims=a.n_sims)
    if o.state.value == 'PASS' and a.seal:
        import datetime as _dt
        from nfl.prospective import showdown_family as SF
        st = json.loads(pathlib.Path(a.state).read_text())
        ko = _dt.datetime.fromisoformat(st['kickoff_et_naive']).replace(
            tzinfo=SF.ZoneInfo('America/New_York')).astimezone(_dt.timezone.utc)
        now = _dt.datetime.now(_dt.timezone.utc)
        sealed = SF.seal(st['game_id'], proj_path=a.projections, draws_path=str(OUT), state_path=a.state,
                         export_path=a.export, inactives_path=a.inactives,
                         kickoff_utc=ko.isoformat().replace('+00:00', 'Z'),
                         written_at=now.isoformat().replace('+00:00', 'Z'), written_at_basis='LIVE_CLOCK',
                         prospective_evidence=(now < ko), model_configuration=f'{a.model_configuration}_{a.n_sims}',
                         reason=('' if now < ko else 'sealed after kickoff: descriptive only'))
        print('SEAL', sealed.state.value, sealed.code, (sealed.detail or '')[:120])
    print(o.state.value, o.code)
    print(' ', o.detail)
    for k, v in (o.evidence or {}).items():
        if k != 'top_means':
            print(f'  {k}: {str(v)[:160]}')
    for k, v in ((o.evidence or {}).get('top_means') or {}).items():
        print(f'    {k:28s} {v}')
    return 0 if o.state.value == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
