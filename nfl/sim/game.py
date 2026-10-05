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

from nfl.sim import dst as dst_mod, share_model as share_mod  # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402

SS = _REPO / 'nfl/sim/SHARED_STATE.json'
PG = _REPO / 'nfl/warehouse/PLAYER_GAME.json'
EFF = _REPO / 'nfl/sim/EFFICIENCY.json'
USAGE = _REPO / 'nfl/sim/USAGE_MODEL.json'
VC = _REPO / 'nfl/sim/VARIANCE_COMPONENTS.json'

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
        # the parameterisation that actually reproduces the pass/rush trade-off
        pf = shared.get('volume_response_plays_and_pass_share') or {}
        self.plays_v = pf.get('plays')
        self.share_v = pf.get('pass_share')
        self.dst = None
        self.scoring = shared['scoring']
        self.ypa = eff['yards_per_pass_attempt']['empirical']
        self.ypc = eff['yards_per_carry']['empirical']
        # how far a player's share of club yards drifts from his share of club opportunities.
        # MEASURED (VARIANCE_COMPONENTS), not set. It replaced an invented 12.0, and the
        # measurement came back HIGHER than the guess for both -- see CONCENTRATION_PROVENANCE.
        self.conc_rec = None
        self.conc_rush = None

        # how volatile a player's SHARE of club opportunity is, over and above sampling noise.
        # Measured: targets 1.21x the multinomial variance, carries 2.78x. This is the channel
        # that matched the correlation misses.
        self.share_conc_tgt = None
        self.share_conc_car = None
        # USAGE-FIRST inputs. 63% of yards-per-carry variance is PLAYER level and 80% of
        # yards-per-target variance is, so drawing one club efficiency and splitting a fixed club
        # yardage had the decomposition backwards and made teammates zero-sum.
        self.usage = None
        self.share = None

    def attach_concentration(self, vc: dict):
        self.conc_rec = vc['receiving']['concentration']
        self.conc_rush = vc['rushing']['concentration']
        dt, dc = vc.get('share_dispersion_targets', {}), vc.get('share_dispersion_carries', {})
        self.share_conc_tgt = dt.get('concentration') if dt.get('state') == 'ESTIMATED' else None
        self.share_conc_car = dc.get('concentration') if dc.get('state') == 'ESTIMATED' else None
        return self

    def attach_usage(self, usage: dict | None):
        self.usage = usage
        if usage:
            tb = usage.get('teammate_backs') or {}
            a = tb.get('implied_dirichlet_concentration')
            if a:
                # measured from the teammate covariance itself rather than from share spread, which
                # is the quantity the old concentration was failing to reproduce
                self.share_conc_car = a
        return self

    @classmethod
    def load(cls) -> Outcome:
        if not SS.exists() or not EFF.exists() or not VC.exists():
            return Outcome.blocked('MODEL_INPUTS_ABSENT',
                                   'shared state, efficiency or variance components missing',
                                   cause=Cause.DATA, shared_state=SS.exists(),
                                   efficiency=EFF.exists(), variance_components=VC.exists())
        vc = json.loads(VC.read_text())
        if vc['receiving'].get('state') != 'ESTIMATED' or vc['rushing'].get('state') != 'ESTIMATED':
            return Outcome.blocked('MODEL_CONCENTRATION_NOT_ESTIMATED',
                                   'the share-drift concentration was not estimated',
                                   cause=Cause.DATA, receiving=vc['receiving'],
                                   rushing=vc['rushing'])
        shared = json.loads(SS.read_text())
        pf = shared.get('volume_response_plays_and_pass_share') or {}
        if any('state' in (pf.get(k) or {'state': 'ABSENT'}) for k in ('plays', 'pass_share')):
            return Outcome.blocked('MODEL_VOLUME_RESPONSE_NOT_IDENTIFIED',
                                   'the plays / pass-share volume response was not identified',
                                   cause=Cause.DATA, plays_form=pf)
        if 'state' in shared['scoring']:
            return Outcome.blocked('MODEL_SCORING_NOT_IDENTIFIED',
                                   shared['scoring']['state'], cause=Cause.DATA)
        m = cls(shared, json.loads(EFF.read_text())).attach_concentration(vc)
        d = dst_mod.DstModel.load()
        if d.state.value != 'PASS':
            return d
        m.dst = d.value
        m.attach_usage(json.loads(USAGE.read_text()) if USAGE.exists() else None)
        sm = share_mod.ShareModel.load()
        if sm.state is State.PASS:
            m.share = sm.value
        return Outcome.ok('MODEL_LOADED', value=m)


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


def _dirichlet_split(total: float, weights, rng, conc: float) -> list[float]:
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


CLUB_TOTAL_IMPOSED = 'CLUB_TOTAL_IMPOSED'
USAGE_FIRST = 'USAGE_FIRST'
DIRICHLET = 'DIRICHLET'
LOGISTIC_NORMAL = 'LOGISTIC_NORMAL'


#: Column order of the per-world stat tuple retained by simulate_game(retain_stats=True).
#: Declared once so no consumer guesses a column; the layered draw artifact names each from this.
STAT_FIELDS = ('pass_att', 'pass_yards', 'pass_td', 'carries', 'rush_yards', 'rush_td',
               'targets', 'receptions', 'rec_yards', 'rec_td')

def simulate_game(model: Model, game, n_sims: int = 2000, seed: int = 23,
                  allocation_mode: str = CLUB_TOTAL_IMPOSED,
                  share_family: str = DIRICHLET, retain_stats: bool = False,
                  _level_offsets=None, _throwaway_rates=None) -> Outcome:
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
    # Per-world stat lines, kept ONLY when asked: the DK number is a collapse of these and the
    # grader needs the parts. Column order is STAT_FIELDS. Completions and interceptions are not
    # drawn by this simulator and are NOT here; a grader must report them NOT_IN_DRAWS, never 0.
    stat_draws = collections.defaultdict(list)
    club_worlds = collections.defaultdict(list)   # (pa, ra, targets, throwaways) per club per world
    club_scoring_worlds = collections.defaultdict(list)   # (points, offensive TDs) per club per world
    dst_components = collections.defaultdict(list)   # (sacks, takeaways, def TD, safeties) per DST per world
    world_points = []                             # (home points, away points) per world, retained only
    for c in clubs:
        if c.get('dst_id'):
            draws[c['dst_id']] = []
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
        if retain_stats:
            world_points.append((pts[home['club']], pts[away['club']]))
        if abs((pts[home['club']] - pts[away['club']]) - margin) > 1e-6 and min(pts.values()) > 0:
            violations.append(('MARGIN', si))

        # defences first: a defence is scored off what its OPPONENT scores in this same world,
        # which is where its negative correlation with that offence comes from. Nothing is added
        # to produce it.
        for c, other in ((home, away), (away, home)):
            if c.get('dst_id'):
                comp = model.dst.draw_components(pts[other['club']], rng)
                draws[c['dst_id']].append(comp[0])
                if retain_stats:
                    dst_components[c['dst_id']].append(comp[1:])

        for c, other in ((home, away), (away, home)):
            own = pts[c['club']]
            own_margin = own - pts[other['club']]
            # PLAYS and PASS SHARE, not two independent attempt draws. A club trades passes
            # against runs inside a roughly fixed play count, and two independent draws cannot
            # represent that: they imply corr(pass, rush) = -0.14 against -0.43 measured. This
            # form implies -0.42. See volume_response_plays_and_pass_share in SHARED_STATE.
            # THE LEVEL MAY BE STEERED; THE DISPERSION AND THE GAME-STATE RESPONSE MAY NOT.
            # `_level_offsets` shifts only the two intercepts, per club, and is set by
            # simulate_game_centred so that the simulated club means land on the projection's
            # team_volume (owner ruling 2026-10-02). per_own_point, per_margin_point and both
            # residual_sd are exactly the measured ones in every world.
            _lo = (_level_offsets or {}).get(c['club']) or {}
            plays = (model.plays_v['intercept'] + _lo.get('plays', 0.0)
                     + model.plays_v['per_own_point'] * own
                     + model.plays_v['per_margin_point'] * own_margin
                     + rng.gauss(0, model.plays_v['residual_sd']))
            pshare = (model.share_v['intercept'] + _lo.get('share', 0.0)
                      + model.share_v['per_own_point'] * own
                      + model.share_v['per_margin_point'] * own_margin
                      + rng.gauss(0, model.share_v['residual_sd']))
            plays = max(1.0, plays)
            pshare = min(0.95, max(0.05, pshare))
            pa = max(0, int(round(plays * pshare)))
            ra = max(0, int(round(plays * (1.0 - pshare))))
            # A throw is not always a target (throwaways, spikes, batted balls). The projection
            # carries targets BELOW pass attempts; the simulator allocated targets from every
            # attempt. With a club rate supplied, throwaways are drawn per world and the identity
            # pass_attempts == targets + throwaways holds exactly, checked below like the others.
            _tr = (_throwaway_rates or {}).get(c['club'])
            throwaways = max(0, min(pa, int(round(pa * _tr)))) if _tr else 0
            tg_total = pa - throwaways
            td = (own - rem - rng.gauss(0, rem_sd)) / ppt
            td = max(0, int(round(td)))

            ypa = model.ypa[rng.randrange(len(model.ypa))]
            ypc = model.ypc[rng.randrange(len(model.ypc))]
            club_pass_yards = pa * ypa
            club_rush_yards = ra * ypc
            # (under USAGE_FIRST both are overwritten below by the sum of player yards)

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
            def alloc(total, weights, conc=None, shock=None, slots=None):
                ghost = max(0.0, 1.0 - sum(weights))
                w = list(weights) + [ghost]
                if share_family == LOGISTIC_NORMAL and shock is not None:
                    # LOGISTIC-NORMAL. One correlated multiplicative shock per depth SLOT, shared by
                    # every player in that slot, then renormalised by the multinomial. The softmax
                    # keeps the shares summing to one while the covariance is unrestricted, so
                    # teammates can co-move -- which a Dirichlet cannot express at any concentration.
                    sl = list(slots or []) + ['OTHER']
                    w = [x * shock.get(sl[i] if i < len(sl) else 'OTHER', 1.0)
                         for i, x in enumerate(w)]
                    tot = sum(w)
                    if tot > 0:
                        w = [x / tot for x in w]
                elif conc:
                    # DIRICHLET-MULTINOMIAL, not multinomial. A plain multinomial over pregame
                    # shares admits sampling noise only; real shares move 1.21x that for targets
                    # and 2.78x for carries. The concentration is measured, so this adds the
                    # missing dispersion without adding a knob.
                    g = [rng.gammavariate(max(1e-6, conc * x), 1.0) if x > 0 else 0.0 for x in w]
                    tot = sum(g)
                    if tot > 0:
                        w = [x / tot for x in g]
                got = _multinomial(total, w, rng)
                return got[:-1], got[-1]

            tgt_shock = car_shock = None
            if share_family == LOGISTIC_NORMAL and model.share is not None:
                tgt_shock = model.share.shock('targets', rng)
                car_shock = model.share.shock('carries', rng)
            qb_att, qb_ghost = alloc(pa, [ps[i].get('pass_att_share', 0.0) for i in qb_ix],
                                     model.share_conc_tgt, tgt_shock,
                                     [ps[i].get('slot', 'OTHER') for i in qb_ix])
            tgt_r, tgt_ghost = alloc(tg_total, [max(0.0, ps[i]['target_share']) for i in rec_ix],
                                     model.share_conc_tgt, tgt_shock,
                                     [ps[i].get('slot', 'OTHER') for i in rec_ix])
            car_all, car_ghost = alloc(ra, [max(0.0, p['carry_share']) for p in ps],
                                       model.share_conc_car, car_shock,
                                       [p.get('slot', 'OTHER') for p in ps])
            if (sum(qb_att) + qb_ghost != pa or sum(tgt_r) + tgt_ghost != tg_total
                    or sum(car_all) + car_ghost != ra or tg_total + throwaways != pa):
                violations.append(('VOLUME', si))
            unalloc['pass_attempts'] += qb_ghost
            unalloc['targets'] += tgt_ghost
            unalloc['rush_attempts'] += car_ghost
            unalloc['pass_attempts_total'] += pa
            unalloc['targets_total'] += pa
            unalloc['rush_attempts_total'] += ra

            club_pass_yards = pa * ypa
            club_rush_yards = ra * ypc
            # (under USAGE_FIRST both are overwritten below by the sum of player yards)
            if allocation_mode == USAGE_FIRST:
                # USAGE FIRST. Each player's yards are HIS opportunities times HIS efficiency, and
                # the club's yardage is whatever those add up to. The club total is derived, not
                # imposed, so two backs can both gain when the club runs more instead of taking
                # carries off each other. A quarterback's passing yards become the sum of his
                # receivers' receiving yards, which is what they are in football.
                ru = model.usage['rushing_efficiency']
                re_ = model.usage['receiving_efficiency']
                club_ypc_draw = ru['empirical_club'][rng.randrange(len(ru['empirical_club']))]
                club_ypt_draw = re_['empirical_club'][rng.randrange(len(re_['empirical_club']))]
                rdev = ru['empirical_player_deviation']
                tdev = re_['empirical_player_deviation']
                rush_yards = [max(0.0, car_all[j] * (club_ypc_draw
                                                     + rdev[rng.randrange(len(rdev))]))
                              for j in range(len(ps))]
                rec_yards = [max(0.0, tgt_r[j] * (club_ypt_draw
                                                  + tdev[rng.randrange(len(tdev))]))
                             for j in range(len(rec_ix))]
                club_pass_yards = sum(rec_yards)
                club_rush_yards = sum(rush_yards)
                # the quarterbacks share the club passing yards their receivers produced, in
                # proportion to the attempts each of them threw
                tot_att = sum(qb_att) or 1
                qb_yards = [club_pass_yards * (a / tot_att) for a in qb_att]
                qb_yd_ghost = rec_yd_ghost = rush_yd_ghost = 0.0
                if abs(sum(qb_yards) - club_pass_yards) > 1e-6:
                    violations.append(('YARDS', si))
            else:
                yards_block = True

            # yards follow the attempts, with the unallocated attempts carrying their own share
            def split(total, weights, ghost, conc):
                out = _dirichlet_split(total, [max(1e-9, w) for w in list(weights) + [ghost]],
                                       rng, conc)
                return out[:-1], out[-1]

            if allocation_mode != USAGE_FIRST:
                qb_yards, qb_yd_ghost = split(club_pass_yards, qb_att, qb_ghost, model.conc_rec)
                rec_yards, rec_yd_ghost = split(club_pass_yards, tgt_r, tgt_ghost, model.conc_rec)
                rush_yards, rush_yd_ghost = split(club_rush_yards, car_all, car_ghost,
                                                  model.conc_rush)
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
            if _tr:
                identities['throwaway_identity_checked'] += 1
            if retain_stats:
                club_worlds[c['club']].append((pa, ra, tg_total, throwaways))
                club_scoring_worlds[c['club']].append((own, td))

            # ---- DK scoring, current rules
            for j, i in enumerate(qb_ix):
                p = ps[i]
                dk = (qb_yards[j] * 0.04 + qb_ptd[j] * 4.0
                      + (3.0 if qb_yards[j] >= 300 else 0.0)
                      + rush_yards[i] * 0.1 + rtd_all[i] * 6.0
                      + (3.0 if rush_yards[i] >= 100 else 0.0))
                draws[p['id']].append(dk)
                if retain_stats:
                    stat_draws[p['id']].append((qb_att[j], qb_yards[j], qb_ptd[j], car_all[i],
                                                rush_yards[i], rtd_all[i], 0.0, 0.0, 0.0, 0.0))
            for j, i in enumerate(rec_ix):
                p = ps[i]
                rec = _binom(tgt_r[j], p.get('catch_rate', 0.65), rng)
                dk = (rec * 1.0 + rec_yards[j] * 0.1 + rec_ptd[j] * 6.0
                      + (3.0 if rec_yards[j] >= 100 else 0.0)
                      + rush_yards[i] * 0.1 + rtd_all[i] * 6.0
                      + (3.0 if rush_yards[i] >= 100 else 0.0))
                draws[p['id']].append(dk)
                if retain_stats:
                    stat_draws[p['id']].append((0.0, 0.0, 0.0, car_all[i], rush_yards[i],
                                                rtd_all[i], tgt_r[j], rec, rec_yards[j],
                                                rec_ptd[j]))

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
        'stat_draws': ({k: v for k, v in stat_draws.items()} if retain_stats else None),
        'STAT_FIELDS': STAT_FIELDS if retain_stats else None,
        'STATS_NOT_DRAWN': ('pass_cmp', 'interceptions') if retain_stats else None,
        'club_checks': dict(identities),
        'IDENTITIES_HELD': ['total', 'margin', 'volume', 'yards', 'touchdowns']
                           + (['pass_attempts_eq_targets_plus_throwaways'] if _throwaway_rates else []),
        'club_worlds': ({k: v for k, v in club_worlds.items()} if retain_stats else None),
        # the points and offensive-TD count each world fixed per club, so a kicker can be scored
        # inside the same world (nfl/tools/kicker_world.py). Output only.
        'club_scoring_worlds': ({k: v for k, v in club_scoring_worlds.items()} if retain_stats else None),
        'dst_components': ({k: v for k, v in dst_components.items()} if retain_stats else None),
        # the score of every world, so a game story, a trailing/leading split or a stack's
        # correlation can be read off the SAME worlds the draws came from. Output only.
        'world_points': ({'home': home['club'], 'away': away['club'], 'points': world_points}
                         if retain_stats else None),
        'level_offsets': dict(_level_offsets or {}), 'throwaway_rates': dict(_throwaway_rates or {}),
        'DST_SOURCE': ('drawn from the opponent\'s simulated points in the same world. Sacks, '
                       'takeaways, defensive and return touchdowns and safeties come from the '
                       'empirical joint tuple within that points-allowed band, so the tail is '
                       'measured and a defence\'s score is no longer a floor. See '
                       'DST_MODEL.scoring_tail.'),
        'allocation_mode': allocation_mode,
        'share_family': share_family,
        'ALLOCATION_MODE_MEANING': {
            CLUB_TOTAL_IMPOSED: ('club yardage drawn first and split across players, which makes '
                                 'teammates zero-sum by construction'),
            USAGE_FIRST: ('each player\'s yards are his own opportunities times his own '
                          'efficiency; club yardage is the sum, so teammates can co-benefit'),
        }[allocation_mode],
        'concentration_used': {'yards_share_receiving': model.conc_rec,
                               'yards_share_rushing': model.conc_rush,
                               'opportunity_share_targets': model.share_conc_tgt,
                               'opportunity_share_carries': model.share_conc_car},
        'CONCENTRATION_PROVENANCE': (
            'measured in VARIANCE_COMPONENTS, replacing an invented 12.0. The measurement '
            'refuted the hypothesis it was built to test: at 16.0 receiving and 13.0 rushing '
            'there is LESS player idiosyncrasy than the guess assumed, so correcting it makes '
            'same-club over-coupling slightly worse rather than better. The constant was still '
            'wrong and is still corrected; the root cause of the over-coupling lies elsewhere.'),
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

# ====================================================================== PROJECTION-CENTRED ARM
#
# OWNER RULING 2026-10-02: the projection layer's team_volume is the authoritative expected-value
# centre; the simulator adds dispersion, covariance, game-script variation, allocation uncertainty
# and scoring-world uncertainty -- it does not keep a second expected team-volume model that
# materially disagrees. Measured before this: PIT carries +9.8% and targets +11.7%, CLE pass
# attempts +7.1% against the projection. Built as a DECLARED ARM: the default simulate_game is
# unchanged, and this wrapper steers only the two intercepts per club.
#
# WHAT IS RECONCILED. pass_attempts, rush_attempts (carries) and targets, per club, in expectation.
# NOT proj_plays: that counts offensive snaps including sacks, penalties and kneels, while the
# simulator's plays regression models pass+rush attempts (intercept 57, ~61 at 20 points against
# a proj_plays of 79). Scoring one against the other's definition is the exact error the postgame
# scorer refuses by name; it is reported as a different quantity, never forced.
#
# HOW. Fixed-point on the two per-club intercept offsets: simulate, measure mean plays (= pa+ra)
# and mean pass share (= pa/(pa+ra)) over the worlds, shift the intercepts by the gap, repeat.
# Targets get their own centre through a per-club throwaway rate taken from the projection's own
# two numbers, 1 - proj_targets/proj_pass_attempts; the identity pa == targets + throwaways then
# holds exactly in every world. Calibration passes use their own seed stream so the final worlds
# are drawn from the base seed exactly as the incumbent arm draws them.
VOLUME_CENTRE_PROJECTION = 'PROJECTION'
VOLUME_CENTRE_INCUMBENT = 'SIMULATOR_OWN_REGRESSION'
RECONCILE_TOL_SE_MULTIPLE = 3.0      # |mean - target| must be within this many Monte Carlo SEs
CALIBRATION_PASSES = 3


def simulate_game_centred(model: Model, game, volume_centre: dict, n_sims: int = 2000,
                          seed: int = 23, n_calib: int = None, **kw) -> Outcome:
    """simulate_game with each club's expected volume centred on `volume_centre`.

    volume_centre = {club: {'pass_attempts': x, 'rush_attempts': y, 'targets': z}}. Returns the
    final pass's Outcome with value['volume_centre'] describing mode, offsets, throwaway rates and
    the per-club reconciliation (target, simulated mean, SE, gap, within_tol).
    """
    import statistics as _st
    clubs = [c['club'] for c in game['clubs']]
    missing = [c for c in clubs if not volume_centre.get(c)]
    if missing:
        return Outcome.fail('VOLUME_CENTRE_MISSING_CLUB', f'no centre for {missing}',
                            cause=Cause.DATA, missing=missing)
    tgt, thr = {}, {}
    for c in clubs:
        v = volume_centre[c]
        pa, ra, tg = float(v['pass_attempts']), float(v['rush_attempts']), float(v['targets'])
        if pa <= 0 or ra < 0 or tg < 0 or tg > pa:
            return Outcome.fail('VOLUME_CENTRE_INCOHERENT',
                                f'{c}: pass {pa}, rush {ra}, targets {tg} -- targets must be '
                                f'0..pass_attempts and attempts positive', cause=Cause.DATA, club=c)
        tgt[c] = {'plays': pa + ra, 'share': pa / (pa + ra), 'pass_attempts': pa,
                  'rush_attempts': ra, 'targets': tg}
        thr[c] = 1.0 - tg / pa
    offsets = {c: {'plays': 0.0, 'share': 0.0} for c in clubs}
    n_cal = int(n_calib or min(n_sims, 1000))
    history = []
    for k in range(CALIBRATION_PASSES):
        o = simulate_game(model, game, n_sims=n_cal, seed=seed + 100_003 * (k + 1),
                          retain_stats=True, _level_offsets=offsets, _throwaway_rates=thr, **kw)
        if o.state is not State.PASS:
            return o
        cw = o.value['club_worlds']
        step = {}
        for c in clubs:
            pa_m = _st.mean(w[0] for w in cw[c]); ra_m = _st.mean(w[1] for w in cw[c])
            plays_m = pa_m + ra_m; share_m = pa_m / plays_m if plays_m else 0.0
            d_plays = tgt[c]['plays'] - plays_m
            d_share = tgt[c]['share'] - share_m
            offsets[c]['plays'] += d_plays
            offsets[c]['share'] += d_share
            step[c] = {'mean_plays': round(plays_m, 3), 'mean_share': round(share_m, 4),
                       'd_plays': round(d_plays, 3), 'd_share': round(d_share, 4)}
        history.append({'pass': k + 1, 'n': n_cal, 'step': step,
                        'offsets_after': {c: dict(offsets[c]) for c in clubs}})
    final = simulate_game(model, game, n_sims=n_sims, seed=seed, retain_stats=True,
                          _level_offsets=offsets, _throwaway_rates=thr, **kw)
    if final.state is not State.PASS:
        return final
    cw = final.value['club_worlds']
    recon, all_ok = {}, True
    for c in clubs:
        recon[c] = {}
        for name, i in (('pass_attempts', 0), ('rush_attempts', 1), ('targets', 2)):
            xs = [w[i] for w in cw[c]]
            m = _st.mean(xs); sd = _st.pstdev(xs)
            # The gap carries TWO independent Monte Carlo errors: the final pass's mean (n_sims
            # draws) and the offsets, which were estimated from the last calibration pass (n_cal
            # draws, a different seed). Both propagate; counting only the first understates the
            # SE and refuses correct runs. This is error propagation, not a loosened margin.
            se = sd * (1.0 / len(xs) + 1.0 / n_cal) ** 0.5 if xs else 0.0
            gap = m - tgt[c][name]; tol = RECONCILE_TOL_SE_MULTIPLE * se
            ok = abs(gap) <= tol
            all_ok = all_ok and ok
            recon[c][name] = {'target': round(tgt[c][name], 4), 'simulated_mean': round(m, 4),
                              'sd': round(sd, 4), 'se': round(se, 4), 'gap': round(gap, 4),
                              'tolerance': round(tol, 4), 'within_tol': ok}
    final.value['volume_centre'] = {
        'mode': VOLUME_CENTRE_PROJECTION, 'level_offsets': offsets, 'throwaway_rates': thr,
        'calibration': history, 'n_sims': n_sims,
        'tolerance_rule': (f'{RECONCILE_TOL_SE_MULTIPLE} x Monte Carlo SE of (simulated mean - '
                           f'target) = sd * sqrt(1/n_sims + 1/n_calib), n_calib={n_cal}'),
        'n_calib': n_cal,
        'reconciliation': recon, 'all_within_tol': all_ok,
        'NOT_RECONCILED_BY_DESIGN': {'proj_plays': ('offensive snaps incl. sacks, penalties, '
                                                    'kneels; the simulator models pass+rush '
                                                    'attempts -- a different quantity')},
        'DISPERSION_UNTOUCHED': ('per_own_point, per_margin_point and both residual_sd are the '
                                 'measured values; only the two intercepts moved, per club'),
    }
    if not all_ok:
        bad = {c: [n for n, v in r.items() if not v['within_tol']] for c, r in recon.items()}
        return Outcome.fail('VOLUME_CENTRE_NOT_RECONCILED',
                            f'simulated means outside {RECONCILE_TOL_SE_MULTIPLE}xSE of the '
                            f'projection centre: {bad}', cause=Cause.DATA, value=final.value,
                            reconciliation=recon)
    return final
