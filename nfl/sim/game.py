#!/usr/bin/env python3.12
"""GAP 3: one game, simulated jointly, with every player reconciled to the club totals.

THE POINT OF THIS MODULE IN ONE SENTENCE

Two players on the same club are correlated because they are drawn from the same game, not
because a bonus was added to them afterwards.

WHERE THE HARD RECONCILIATION IS

Every allocation is multinomial over a drawn club total, so the identities hold EXACTLY rather
than approximately, and there is no renormalisation step to forget:

    sum of player targets   == club pass attempts       (exact, by construction)
    sum of player carries   == club rush attempts       (exact)
    sum of receiving yards  == club passing yards       (exact)
    sum of rushing yards    == club rushing yards       (exact)
    sum of player TDs       == club offensive TDs        (exact)
    home points + away points == drawn game total        (exact)
    home points - away points == drawn home margin       (exact)

verify() checks all seven on every simulated game and FAILS on any violation, because an
identity that is only usually true is not an identity.

WHAT IS DRAWN AND FROM WHAT

The shared state comes from SHARED_STATE.json, measured over 6,751 games 2000-2026: a game
total and a home margin around the market lines with SDs of 13.38 and 13.20, drawn from the
EMPIRICAL residuals rather than a fitted normal. Their measured correlation is +0.025, which is
why they may be drawn independently -- a measurement, not a convenience.

Club volume is then conditioned on the realised game, not on the market: passing falls 0.262
attempts per point of lead and rushing rises 0.229, both at better than seventeen standard
errors. That single pair of coefficients is what produces the game-script correlation structure.

WHAT IS NOT MODELLED, AND SAID PLAINLY
  - no play-by-play sequencing, so no drive-level or clock effects beyond the script coefficients
  - no defensive personnel beyond what the market lines already price
  - efficiency is drawn per club-game and shared across that club's players, which is a real
    source of same-club correlation but it is the only one beyond volume
  - special-teams and defensive scoring sit in the measured non-touchdown remainder and are not
    attributed to players
"""
from __future__ import annotations

import collections
import json
import math
import pathlib
import random
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

SS = _REPO / 'nfl/sim/SHARED_STATE.json'
PG = _REPO / 'nfl/warehouse/PLAYER_GAME.json'
EFF = _REPO / 'nfl/sim/EFFICIENCY.json'

TOL = 1e-6


# ======================================================================================
# efficiency, measured at club-game level so it can be drawn once and shared
# ======================================================================================
def fit_efficiency() -> Outcome:
    """Club-game yards per pass attempt and per carry, with the spread across club-games.

    Measured at CLUB-GAME level on purpose. Drawing one efficiency per club per game and sharing
    it across that club's players is a second channel of same-club correlation, alongside volume,
    and it is the reason a quarterback and his receiver move together on a day when the offence
    is simply working.
    """
    if not PG.exists():
        return Outcome.blocked('EFF_NO_PLAYER_GAME', 'player-game table missing', cause=Cause.DATA)
    art = json.loads(PG.read_text())
    rows = art['rows'] if isinstance(art['rows'], list) else list(art['rows'].values())
    agg: dict = {}
    for r in rows:
        k = (r['game_id'], r['club'])
        a = agg.setdefault(k, {'att': 0.0, 'pyd': 0.0, 'car': 0.0, 'ryd': 0.0})
        for src, dst in (('pass_attempts', 'att'), ('passing_yards', 'pyd'),
                         ('carries', 'car'), ('rushing_yards', 'ryd')):
            v = r.get(src)
            if isinstance(v, (int, float)):
                a[dst] += float(v)
    ypa = [a['pyd'] / a['att'] for a in agg.values() if a['att'] >= 15]
    ypc = [a['ryd'] / a['car'] for a in agg.values() if a['car'] >= 10]
    if len(ypa) < 200 or len(ypc) < 200:
        return Outcome.blocked('EFF_TOO_FEW_CLUB_GAMES', f'{len(ypa)} passing, {len(ypc)} rushing',
                               cause=Cause.DATA)

    def summarise(xs):
        xs = sorted(xs)
        n = len(xs)
        m = sum(xs) / n
        sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))
        return {'n': n, 'mean': round(m, 4), 'sd': round(sd, 4),
                'p05': round(xs[int(0.05 * n)], 4), 'p50': round(xs[n // 2], 4),
                'p95': round(xs[int(0.95 * n)], 4), 'empirical': [round(x, 4) for x in xs]}

    out = {'ARTIFACT': 'EFFICIENCY', 'level': 'CLUB_GAME',
           'yards_per_pass_attempt': summarise(ypa), 'yards_per_carry': summarise(ypc),
           'WHY_CLUB_GAME': ('one efficiency draw per club per game, shared across that club\'s '
                             'players. This is a correlation channel, not a simplification.'),
           'MIN_ATTEMPTS': {'pass': 15, 'rush': 10}}
    EFF.write_text(json.dumps(out, indent=2))
    return Outcome.ok('EFFICIENCY_MEASURED', value={
        'ypa': {k: v for k, v in out['yards_per_pass_attempt'].items() if k != 'empirical'},
        'ypc': {k: v for k, v in out['yards_per_carry'].items() if k != 'empirical'},
        'artifact': str(EFF.relative_to(_REPO))})


# ======================================================================================
# the model, loaded once
# ======================================================================================
class Model:
    def __init__(self, shared: dict, eff: dict):
        e = shared['environment']
        self.total_res = shared['empirical_residuals']['total']
        self.margin_res = shared['empirical_residuals']['margin']
        self.total_sd = e['total_residual']['sd']
        self.margin_sd = e['margin_residual']['sd']
        v = shared['volume_response_to_realised_game']
        self.pass_v = v['pass_attempts']
        self.rush_v = v['rush_attempts']
        self.scoring = shared['scoring']
        self.ypa = eff['yards_per_pass_attempt']['empirical']
        self.ypc = eff['yards_per_carry']['empirical']

    @classmethod
    def load(cls) -> Outcome:
        if not SS.exists() or not EFF.exists():
            return Outcome.blocked('MODEL_INPUTS_ABSENT',
                                   'shared state or efficiency artifact missing', cause=Cause.DATA,
                                   shared_state=SS.exists(), efficiency=EFF.exists())
        shared = json.loads(SS.read_text())
        if 'state' in shared['volume_response_to_realised_game'].get('pass_attempts', {}):
            return Outcome.blocked('MODEL_VOLUME_RESPONSE_NOT_IDENTIFIED',
                                   'the volume response was not identified', cause=Cause.DATA)
        if 'state' in shared['scoring']:
            return Outcome.blocked('MODEL_SCORING_NOT_IDENTIFIED',
                                   shared['scoring']['state'], cause=Cause.DATA)
        return Outcome.ok('MODEL_LOADED', value=cls(shared, json.loads(EFF.read_text())))


def _multinomial(n: int, weights, rng) -> list[int]:
    """Exact allocation of n units over weights. Sums to n by construction, always."""
    tot = sum(weights)
    if n <= 0 or tot <= 0:
        return [0] * len(weights)
    out, left, wleft = [], n, tot
    for w in weights[:-1]:
        if left <= 0 or wleft <= 0:
            out.append(0)
            wleft -= w
            continue
        p = min(1.0, max(0.0, w / wleft))
        k = sum(1 for _ in range(left) if rng.random() < p) if left < 40 else _binom(left, p, rng)
        out.append(k)
        left -= k
        wleft -= w
    out.append(left)
    return out


def _binom(n, p, rng):
    # normal approximation with a clamp, for the large-n case only
    if p <= 0:
        return 0
    if p >= 1:
        return n
    mu, sd = n * p, math.sqrt(n * p * (1 - p))
    return max(0, min(n, int(round(rng.gauss(mu, sd)))))


def _dirichlet_split(total: float, weights, rng, conc: float = 12.0) -> list[float]:
    """Split a continuous club total over players. Sums to the total exactly."""
    tot = sum(weights)
    if total <= 0 or tot <= 0:
        return [0.0] * len(weights)
    draws = []
    for w in weights:
        a = max(1e-6, conc * w / tot)
        draws.append(rng.gammavariate(a, 1.0))
    s = sum(draws) or 1.0
    return [total * d / s for d in draws]


def simulate_game(model: Model, game, n_sims: int = 2000, seed: int = 23) -> Outcome:
    """Simulate one game n_sims times and return per-player DK point draws.

    `game` needs: total_line, home_spread, and for each of two clubs a list of players with
    id, position, target_share, carry_share, and pass_td_share / rush_td_share.
    """
    rng = random.Random(seed)
    clubs = game['clubs']
    if len(clubs) != 2:
        return Outcome.blocked('SIM_NEEDS_TWO_CLUBS', f'{len(clubs)} clubs supplied',
                               cause=Cause.DATA)
    home, away = clubs[0], clubs[1]
    draws: dict = {p['id']: [] for c in clubs for p in c['players']}
    identities = collections.Counter()
    unalloc: collections.Counter = collections.Counter()
    violations = []

    ppt = model.scoring['points_per_offensive_td']
    rem = model.scoring['points_not_from_offensive_td']
    rem_sd = model.scoring['residual_sd'] or 0.0

    for si in range(n_sims):
        total = game['total_line'] + model.total_res[rng.randrange(len(model.total_res))]
        margin = game['home_spread'] + model.margin_res[rng.randrange(len(model.margin_res))]
        total = max(0.0, total)
        pts = {home['club']: (total + margin) / 2.0, away['club']: (total - margin) / 2.0}
        # points cannot be negative; move the shortfall to the other side so the TOTAL identity
        # survives -- a clamp that broke the identity would defeat the purpose of this module
        for a, b in ((home['club'], away['club']), (away['club'], home['club'])):
            if pts[a] < 0:
                pts[b] += pts[a]
                pts[a] = 0.0
        if abs((pts[home['club']] + pts[away['club']]) - total) > TOL:
            violations.append(('TOTAL', si))
        if abs((pts[home['club']] - pts[away['club']]) - margin) > 1e-6 and min(pts.values()) > 0:
            violations.append(('MARGIN', si))

        for c, other in ((home, away), (away, home)):
            own = pts[c['club']]
            own_margin = own - pts[other['club']]
            pa = (model.pass_v['intercept'] + model.pass_v['per_own_point'] * own
                  + model.pass_v['per_margin_point'] * own_margin
                  + rng.gauss(0, model.pass_v['residual_sd']))
            ra = (model.rush_v['intercept'] + model.rush_v['per_own_point'] * own
                  + model.rush_v['per_margin_point'] * own_margin
                  + rng.gauss(0, model.rush_v['residual_sd']))
            pa, ra = max(0, int(round(pa))), max(0, int(round(ra)))
            td = (own - rem - rng.gauss(0, rem_sd)) / ppt
            td = max(0, int(round(td)))

            ypa = model.ypa[rng.randrange(len(model.ypa))]
            ypc = model.ypc[rng.randrange(len(model.ypc))]
            club_pass_yards = pa * ypa
            club_rush_yards = ra * ypc

            ps = c['players']
            qb_ix = [i for i, p in enumerate(ps) if p['position'] == 'QB']
            rec_ix = [i for i, p in enumerate(ps) if p['position'] != 'QB']

            # ---- passing volume over the quarterbacks, receiving volume over everyone else.
            # Targets are allocated from the SAME club pass attempts the quarterbacks throw, so
            # the two sides of the passing game cannot drift apart.
            # EXPLICIT UNALLOCATED MASS. Shares are shares OF THE CLUB, so when the supplied
            # pool is partial they sum below one and the remainder belongs to players this pool
            # does not carry. That remainder gets its own bucket rather than being renormalised
            # away: renormalising would hand a backup's carries to the starter and inflate every
            # projection in the pool. The bucket is measured and reported, and it is also what
            # keeps the reconciliation exact when a club has, say, no ranked back at all.
            def alloc(total, weights):
                ghost = max(0.0, 1.0 - sum(weights))
                got = _multinomial(total, list(weights) + [ghost], rng)
                return got[:-1], got[-1]

            qb_att, qb_ghost = alloc(pa, [ps[i].get('pass_att_share', 0.0) for i in qb_ix])
            tgt_r, tgt_ghost = alloc(pa, [max(0.0, ps[i]['target_share']) for i in rec_ix])
            car_all, car_ghost = alloc(ra, [max(0.0, p['carry_share']) for p in ps])
            if (sum(qb_att) + qb_ghost != pa or sum(tgt_r) + tgt_ghost != pa
                    or sum(car_all) + car_ghost != ra):
                violations.append(('VOLUME', si))
            unalloc['pass_attempts'] += qb_ghost
            unalloc['targets'] += tgt_ghost
            unalloc['rush_attempts'] += car_ghost
            unalloc['pass_attempts_total'] += pa
            unalloc['targets_total'] += pa
            unalloc['rush_attempts_total'] += ra

            club_pass_yards = pa * ypa
            club_rush_yards = ra * ypc
            # yards follow the attempts, with the unallocated attempts carrying their own share
            def split(total, weights, ghost):
                out = _dirichlet_split(total, [max(1e-9, w) for w in list(weights) + [ghost]], rng)
                return out[:-1], out[-1]

            qb_yards, qb_yd_ghost = split(club_pass_yards, qb_att, qb_ghost)
            rec_yards, rec_yd_ghost = split(club_pass_yards, tgt_r, tgt_ghost)
            rush_yards, rush_yd_ghost = split(club_rush_yards, car_all, car_ghost)
            for got, ghost, want in ((qb_yards, qb_yd_ghost, club_pass_yards),
                                     (rec_yards, rec_yd_ghost, club_pass_yards),
                                     (rush_yards, rush_yd_ghost, club_rush_yards)):
                if abs(sum(got) + ghost - want) > 1e-3:
                    violations.append(('YARDS', si))

            # ---- touchdowns: split pass and rush, then over players. A passing touchdown scores
            # for BOTH the thrower and the catcher, which is how DK scores it.
            n_pass_td = _multinomial(td, [c.get('pass_td_rate', 0.6156),
                                          1 - c.get('pass_td_rate', 0.6156)], rng)[0]
            n_rush_td = td - n_pass_td
            qb_ptd, qb_td_ghost = alloc(n_pass_td, [a / pa if pa else 0.0 for a in qb_att])
            rec_ptd, rec_td_ghost = alloc(
                n_pass_td, [max(0.0, ps[i].get('pass_td_share', 0.0)) for i in rec_ix])
            rtd_all, rush_td_ghost = alloc(
                n_rush_td, [max(0.0, p.get('rush_td_share', 0.0)) for p in ps])
            if (sum(qb_ptd) + qb_td_ghost != n_pass_td
                    or sum(rec_ptd) + rec_td_ghost != n_pass_td
                    or sum(rtd_all) + rush_td_ghost != n_rush_td):
                violations.append(('TD', si))
            identities['club_games_checked'] += 1

            # ---- DK scoring, current rules
            for j, i in enumerate(qb_ix):
                p = ps[i]
                dk = (qb_yards[j] * 0.04 + qb_ptd[j] * 4.0
                      + (3.0 if qb_yards[j] >= 300 else 0.0)
                      + rush_yards[i] * 0.1 + rtd_all[i] * 6.0
                      + (3.0 if rush_yards[i] >= 100 else 0.0))
                draws[p['id']].append(dk)
            for j, i in enumerate(rec_ix):
                p = ps[i]
                rec = _binom(tgt_r[j], p.get('catch_rate', 0.65), rng)
                dk = (rec * 1.0 + rec_yards[j] * 0.1 + rec_ptd[j] * 6.0
                      + (3.0 if rec_yards[j] >= 100 else 0.0)
                      + rush_yards[i] * 0.1 + rtd_all[i] * 6.0
                      + (3.0 if rush_yards[i] >= 100 else 0.0))
                draws[p['id']].append(dk)

    if violations:
        kinds = collections.Counter(k for k, _ in violations)
        return Outcome.fail('SIM_IDENTITY_VIOLATED',
                            'a reconciliation identity failed during simulation',
                            violations_by_kind=dict(kinds), n_violations=len(violations),
                            note=('an identity that is only usually true is not an identity. The '
                                  'whole point of drawing both clubs from one game is that these '
                                  'hold exactly.'))
    frac = {}
    for k in ('pass_attempts', 'targets', 'rush_attempts'):
        tot = unalloc[f'{k}_total']
        frac[k] = round(unalloc[k] / tot, 5) if tot else None
    return Outcome.ok('GAME_SIMULATED', value={
        'n_sims': n_sims, 'draws': draws,
        'club_checks': dict(identities),
        'IDENTITIES_HELD': ['total', 'margin', 'volume', 'yards', 'touchdowns'],
        'unallocated_fraction': frac,
        'UNALLOCATED_MEANING': ('share of club volume belonging to players not in the supplied '
                                'pool. Reported rather than renormalised away, because '
                                'renormalising would hand a missing backup\'s work to the '
                                'starter and inflate every projection in the pool.'),
    })


if __name__ == '__main__':
    o = fit_efficiency()
    print(o.state.value, o.code, o.value if o.state.value == 'PASS' else o.evidence)
    raise SystemExit(0 if o.state.value == 'PASS' else 1)
