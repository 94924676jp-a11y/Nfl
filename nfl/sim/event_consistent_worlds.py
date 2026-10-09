"""Event-consistent published Showdown worlds. A SHADOW ARM: nothing in production calls this module.

    from nfl.sim import event_consistent_worlds as ECW
    o = ECW.build(art, rows_by_key, int_rate, seed)        # art = showdown_draws.build(...).value
    ECW.publish(o.value, out_dir, tag, ...)                  # *_WORLDS.npz + *_DRAWS.json, checker format

WHY THIS EXISTS. `nfl/tools/world_accounting_check.py` measured the published TB@DAL OFFICIAL worlds
(2,000 worlds) breaking ordinary football accounting: club passing yards != receiving yards in 1,928 DAL
and 1,997 TB worlds; receiving yards with no reception in 1,496 worlds; a receiving TD with no reception
in 558; more interceptions thrown than the opposing DST took away in 543 / 409; club points below six
per touchdown in ~65 per club; passing TDs != receiving TDs in 3 TB worlds.

WHERE EACH DEFECT COMES FROM, measured by re-running `showdown_draws.build` on the OFFICIAL inputs
(it reproduces the published DK draws exactly) and checking the RAW worlds before any post-processing:

  PASS_YDS_EQ_REC_YDS   classic_slate_run.efficiency_worlds: one independent yards-per-opportunity factor
                        for the QB's passing yards and another for EACH receiver's receiving yards. The
                        raw worlds are close (mean gap +0.01 DAL, -0.14 TB yds; 22 / 30 worlds over half a
                        yard, from yards split into the simulator's unallocated bucket).
  YDS_WITHOUT_CATCH     RAW SIMULATOR (nfl/sim/game.py). Receiving yards are a Dirichlet split of club
  REC_TD_WITHOUT_CATCH  passing yards over TARGETS, receptions are Binomial(targets, catch rate), and
                        receiving TDs are a multinomial over pass-TD shares -- three independent draws,
                        so a target that was not caught still carries yards and touchdowns. 1,507 / 558
                        raw worlds; the efficiency step only rescales them.
  PASS_TD_EQ_REC_TD     RAW SIMULATOR: share denominators include positions the shares are not given to,
                        so the multinomial's unallocated bucket receives touchdowns (TB, 3 worlds).
  INT_LE_OPP_TAKEAWAYS  efficiency_worlds: interceptions are Binomial(attempts, projection int_rate),
                        drawn without reference to the opposing DST's takeaways in the same world.
  POINTS_GE_6_PER_TD    RAW SIMULATOR: club points are a continuous draw (total and margin residuals) and
                        offensive TDs are an inversion of it, so points are never an event sum.

So the statement that the raw simulator's identities hold and the defects are introduced afterwards is
only half true: two of the six measured defects are introduced afterwards, four are already in the raw
worlds. The simulator's own identity certificate includes the unallocated buckets, which the published
worlds do not carry, and it never checked catch/yard/TD coherence.

WHAT THIS ARM DOES, IN ORDER, PER CLUB AND WORLD (club volumes, targets, receptions and carries are
left exactly as the simulator drew them):

  1. RECEIVING YARDS ARE CAUGHT, NOT TARGETED. Each reception carries the receiver's projected yards per
     CATCH (conditional rec_yards / conditional receptions), times that player-world's raw simulated
     yards-per-target relative to his own mean (so the simulator's club-efficiency draw and player
     deviation -- its measured dispersion and same-club correlation -- are kept). A target that was not
     caught carries nothing.
  2. EFFICIENCY IS ANCHORED ONCE, AT THE CLUB. One factor per club scales those catch yards so the club's
     mean gross passing yards equals the incumbent arm's club mean -- by default the QB side
     (`ANCHOR_QB`: sum of the incumbent's anchored QB passing yards), optionally the receiver side
     (`ANCHOR_REC`). The projection does not close its own passing game (TB receivers +29.9 yds over
     the QB), so BOTH cannot hold; the choice is declared, and the drift it forces is reported.
  3. QUARTERBACK PASSING YARDS ARE THE SUM OF HIS RECEIVERS' YARDS, shared between a club's QBs in
     proportion to the attempts each threw in that world. PASS_YDS == REC_YDS by construction.
  4. A RECEIVING TD IS ONE OF THE WORLD'S CATCHES. The club's passing TDs are placed, one at a time and
     without replacement, on that world's receptions, weighted by each receiver's projected TDs per
     catch. Each is credited to a QB by attempts. PASS_TD == REC_TD and rec_td <= receptions hold by
     construction. A rushing TD likewise is one of the world's carries (rush_td <= carries); the raw
     simulator gave rushing TDs only to RB/QB shares and dropped the rest of the club's rushing TDs into
     its unallocated bucket, so a receiver's projected rushing TDs were never drawn -- here every club
     rushing TD the world scored is placed on a carry.
  5. EVERY INTERCEPTION IS ONE OF THE OPPOSING DST'S TAKEAWAYS. INT ~ Binomial(opposing DST takeaways in
     the same world, q), q = (int_rate x mean club attempts) / mean opposing takeaways -- a moment
     match on two existing measured quantities (the projection's int_rate, the DST model's empirical
     takeaway tuples), so the INT mean equals the incumbent's in expectation. INT <= takeaways always.
  6. CLUB POINTS ARE A SUM OF SCORING EVENTS: 6 x offensive TDs (the TDs actually on player lines) +
     XP made + 2 x two-point tries made + 3 x FG made + 6 x own DST defensive/return TDs + 2 x own DST
     safeties. Tries and FGs come from the same kicker_world rates and the same world points the
     incumbent kicker uses; the kicker's DK score is those events. The DST's DK score is recomputed
     from its components and the event-sum points it allowed (DST tier rule from nfl/sim/dst.py).
  7. DK points of every skill player are recomputed from the published stat line with
     classic_slate_run.dk_from_stats -- the same function the checker uses. No second scoring formula.

NAMED, NOT REPRESENTED (none is faked):
  - laterals, non-QB passes, penalties, negative-yardage plays: the simulator has no such events, so no
    legitimate exception to an identity is available in any world;
  - fumbles lost by a player (DK -1): the DST's non-INT takeaways stand with no fumbling player debited;
  - two-point conversions are in club points but credited to no player's DK line;
  - the try after a DEFENSIVE/RETURN touchdown is not drawn (kicker_world does not credit it either);
  - the DST tuple was drawn in the band of the simulator's CONTINUOUS points allowed; its tier is
    recomputed on the event-sum points (worlds whose band changed are counted, not hidden);
  - DST and kicker draws are NOT rescaled to their projection: a multiplicative rescale would break
    "DK points == DK scoring of the published events". Their drift is reported instead.
  - INTs are tied to the opposing takeaways, not to the world's own attempts (except the cap
    INT <= attempts, counted). The incumbent tied them to attempts and to nothing else.
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

from nfl.sim import dst as dst_mod  # noqa: E402
from nfl.tools import classic_slate_run as CR  # noqa: E402
from sportsplatform.governance.outcome import Outcome  # noqa: E402

SPEC_VERSION = 'event-consistent-worlds-1'
ARM = 'EVENT_CONSISTENT_SHADOW'
ANCHOR_QB = 'CLUB_PASS_YARDS_ON_INCUMBENT_QB_MEAN'
ANCHOR_REC = 'CLUB_PASS_YARDS_ON_INCUMBENT_RECEIVER_SUM'
ANCHORS = (ANCHOR_QB, ANCHOR_REC)
STAT_FIELDS = CR.STAT_FIELDS
WORLD_FIELDS = CR.WORLD_FIELDS          # STAT_FIELDS + ('interceptions',)
_I = {f: i for i, f in enumerate(STAT_FIELDS)}
#: per-world scoring events kept per club, in this order
EVENT_FIELDS = ('off_td', 'pass_td', 'rush_td', 'xp_att', 'xp_made', 'tp_att', 'tp_made', 'fg_made',
                'fg_0_39_made', 'fg_40_49_made', 'fg_50_plus_made', 'def_td', 'safety', 'points')
#: DK club scoring of one event, from the NFL rules (not fitted): TD 6, XP 1, two-point try 2, FG 3, safety 2
POINTS_PER = {'td': 6.0, 'xp': 1.0, 'tp': 2.0, 'fg': 3.0, 'safety': 2.0}

NOT_REPRESENTED = {
    'LATERALS_NON_QB_PASSES_PENALTIES': 'no such events in nfl/sim/game.py; no identity exception is available',
    'NEGATIVE_YARDAGE': 'raw simulator yards are >= 0 per player-world; not represented',
    'FUMBLES_LOST': 'non-INT DST takeaways are not debited to any player (DK -1 fumble lost not drawn)',
    'TWO_POINT_CONVERSIONS_PLAYER_CREDIT': 'in club points, credited to no player DK line',
    'TRY_AFTER_DEFENSIVE_TD': 'not drawn; defensive/return TDs add exactly 6 to club points',
    'DST_BAND_FROM_CONTINUOUS_POINTS': 'DST tuple band chosen by the raw continuous points allowed; tier '
                                       'recomputed on event points; band changes counted',
    'QB_SPLIT_BY_ATTEMPTS': 'with two QBs, yards/TDs/INTs are shared by world attempts (catch-to-passer '
                            'pairing is not simulated)',
    'DST_AND_KICKER_NOT_RESCALED': 'their DK is the DK scoring of the published events; drift reported',
    'DST_POINTS_ALLOWED_DEFINITION': 'all opponent club points (incl. the opponent DST defensive/return TDs and '
                                     'safeties), as the raw simulator used; DK\'s exact treatment of those is not '
                                     'verified here',
    'DRAWN_TOTAL_AND_MARGIN': 'published club points are event sums and no longer equal the simulator\'s drawn '
                              'continuous total/margin; the drawn values still steer volume, TD count and FG count',
    'INT_TO_OWN_ATTEMPTS': 'INTs follow the opposing takeaways (thinned), not the world\'s own attempts, apart from '
                           'the cap INT <= attempts',
}


class _Refuse(Exception):
    def __init__(self, code, detail, **ev):
        super().__init__(detail)
        self.code, self.detail, self.ev = code, detail, ev


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _ratio(a, b):
    return (float(a) / float(b)) if _num(a) and _num(b) and b > 0 and a >= 0 else None


def _rng(seed, *parts):
    """An independent, process-stable stream per (seed, purpose). str seeds hash with SHA-512 in CPython,
    so PYTHONHASHSEED cannot move them."""
    return random.Random('|'.join([str(seed)] + [str(p) for p in parts]))


def _club(key):
    return key.rsplit('|', 1)[1]


def _place(n, capacity, weight, rng):
    """Place n events, one at a time and WITHOUT replacement, on per-player capacity (catches or carries),
    with probability proportional to remaining capacity x per-unit weight. Returns (counts, n_unplaced).
    Falls back to remaining capacity alone when every weighted capacity is zero; an event with no capacity
    left anywhere is UNPLACED and returned as such, never forced onto a player who has no catch/carry."""
    got = [0] * len(capacity)
    left = [int(c) for c in capacity]
    unplaced = 0
    for _ in range(int(n)):
        w = [l * wt for l, wt in zip(left, weight)]
        if sum(w) <= 0:
            w = [float(l) for l in left]
        tot = sum(w)
        if tot <= 0:
            unplaced += 1
            continue
        u, acc, j = rng.random() * tot, 0.0, None
        for i, x in enumerate(w):
            acc += x
            if x > 0 and u <= acc:
                j = i
                break
        if j is None:                       # float edge: last positive bucket
            j = max(i for i, x in enumerate(w) if x > 0)
        got[j] += 1
        left[j] -= 1
    return got, unplaced


def _split_count(n, weights, rng):
    """n indivisible events over weights (multinomial, one at a time). Weights must have a positive sum."""
    out = [0] * len(weights)
    tot = float(sum(weights))
    for _ in range(int(n)):
        u, acc = rng.random() * tot, 0.0
        for i, w in enumerate(weights):
            acc += w
            if w > 0 and u <= acc:
                out[i] += 1
                break
        else:
            out[max(i for i, w in enumerate(weights) if w > 0)] += 1
    return out


def _binom(n, p, rng):
    return sum(1 for _ in range(int(n)) if rng.random() < p)


def kicker_line(points, off_td, mix, rates, rng):
    """One world's kicking events for one club. THE SAME DRAW as nfl/tools/kicker_world.draw -- same rates,
    same rng consumption, same DK -- that additionally returns the two-point tries it drew (kicker_world
    computes them and discards them, and club points need them). Equality with kicker_world.draw under a
    shared seed is a test (nfl/tests/test_event_consistent_worlds.py), so the two cannot drift apart."""
    from nfl.tools import kicker_world as KW
    td = int(off_td)
    tp_att = KW._binom(td, rates['try_rate_2pt'], rng)
    tp_made = KW._binom(tp_att, rates['two_pt_success'], rng)
    xp_att = td - tp_att
    xp_made = KW._binom(xp_att, rates['pat_make_rate'], rng)
    remainder = points - 6 * td - xp_made - 2 * tp_made
    fg_made = max(0, int(round(rates['fg_share'] * remainder / 3.0)))
    bands = list(mix['made_mix'])
    cum, acc = [], 0.0
    for b in bands:
        acc += mix['made_mix'][b]
        cum.append(acc)
    made = collections.Counter()
    for _ in range(fg_made):
        u = rng.random() * acc
        made[next(b for b, c in zip(bands, cum) if u <= c)] += 1
    miss = {b: KW._negbin_failures(made[b], mix['make_rate'][b], rng) for b in bands}
    dk = xp_made + sum(KW.BAND_POINTS[b] * made[b] for b in bands)
    return dk, {'xp_att': xp_att, 'xp_made': xp_made, 'fg_made': fg_made,
                'fg_att': fg_made + sum(miss.values()),
                **{f'{b}_made': made[b] for b in bands},
                'remainder_negative': remainder < 0, 'tp_att': tp_att, 'tp_made': tp_made}


def _kicker_inputs(club, given):
    if given is not None:
        k = given.get(club)
        if not k:
            raise _Refuse('EVENT_WORLDS_NO_KICKER_INPUTS', f'{club}: no kicker mix/rates supplied', club=club)
        return k['mix'], k['rates']
    from nfl.tools import kicker_world as KW
    mix = KW.band_mix(club)
    if mix is None:
        raise _Refuse('EVENT_WORLDS_KICKER_NOT_PROJECTABLE', f'{club}: no measured kicking history', club=club)
    return mix, KW.load()['rates']


def _dst_dk(points_allowed, comp):
    sacks, take, dtd, saf = comp
    return (dst_mod.tier(points_allowed) + dst_mod.SACK_POINTS * sacks + dst_mod.TAKEAWAY_POINTS * take
            + dst_mod.DEFENSIVE_TD_POINTS * dtd + dst_mod.SAFETY_POINTS * saf)


def _band(points):
    for lo, hi in dst_mod.CONDITIONING_BANDS:
        if lo <= points < hi:
            return (lo, hi)
    return dst_mod.CONDITIONING_BANDS[-1]


def build(art: dict, rows_by_key: dict, int_rate: float, seed: int, *, club_pass_anchor: str = ANCHOR_QB,
          kicker_inputs: dict = None, incumbent_seed: int = None) -> Outcome:
    """Event-consistent published worlds from the SAME inputs the incumbent published step takes.

    art          showdown_draws.build(...).value: stat_draws, STAT_FIELDS, world_points, club_scoring_worlds,
                 dst_components, kickers, draws (raw).
    rows_by_key  projection rows keyed 'name|club' (position, conditional_volume, receptions, carries, td).
    int_rate     the projection's int_rate (the incumbent's interception rate).
    seed         base seed; every stream is derived from it by purpose and club.
    incumbent_seed  the seed the incumbent passes to efficiency_worlds (showdown_slate_run: seed + 99). Used
                 only to compute the incumbent's anchored means, which are this arm's club targets.
    """
    try:
        return Outcome.ok('EVENT_WORLDS_BUILT', _build(art, rows_by_key, float(int_rate), seed, club_pass_anchor,
                                                       kicker_inputs, incumbent_seed),
                          f'{ARM}: event-consistent published worlds ({club_pass_anchor})')
    except _Refuse as e:
        return Outcome.fail(e.code, e.detail, **e.ev)


def _build(art, rows_by_key, int_rate, seed, anchor, kicker_inputs, incumbent_seed):
    import numpy as np
    if anchor not in ANCHORS:
        raise _Refuse('EVENT_WORLDS_ANCHOR_UNKNOWN', f'{anchor!r} is not one of {ANCHORS}')
    if tuple(art.get('STAT_FIELDS') or ()) != STAT_FIELDS:
        raise _Refuse('EVENT_WORLDS_STAT_FIELDS', f"STAT_FIELDS {art.get('STAT_FIELDS')} != {STAT_FIELDS}")
    sd = art.get('stat_draws') or {}
    world_pts = art.get('world_points') or {}
    csw = art.get('club_scoring_worlds') or {}
    dcomp = art.get('dst_components') or {}
    if not sd or not world_pts.get('points') or not csw or not dcomp:
        raise _Refuse('EVENT_WORLDS_INPUT_EMPTY', 'stat_draws, world_points, club_scoring_worlds and '
                      'dst_components are all required and non-empty',
                      present={k: bool(art.get(k)) for k in ('stat_draws', 'world_points',
                                                             'club_scoring_worlds', 'dst_components')})
    home, away = world_pts['home'], world_pts['away']
    clubs = (home, away)
    n = len(world_pts['points'])
    keys = sorted(sd)
    missing = [k for k in keys if k not in rows_by_key]
    if missing:
        raise _Refuse('EVENT_WORLDS_NO_PROJECTION_ROW', f'{len(missing)} drawn player(s) have no projection row',
                      players=missing[:10])
    bad_len = sorted({len(v) for v in sd.values()} | {len(csw[c]) for c in clubs if c in csw}) != [n]
    if bad_len or any(c not in csw for c in clubs):
        raise _Refuse('EVENT_WORLDS_RAGGED', f'world counts disagree with {n} world_points')
    dst_key = {}
    for c in clubs:
        ks = [k for k in dcomp if _club(k) == c]
        if len(ks) != 1 or len(dcomp[ks[0]]) != n:
            raise _Refuse('EVENT_WORLDS_DST_COMPONENTS', f'{c}: expected one DST with {n} component worlds, got {ks}')
        dst_key[c] = ks[0]

    S = {k: np.asarray(sd[k], dtype=float) for k in keys}
    # THE INCUMBENT, computed by the incumbent's own function on the same raw worlds. Its anchored means are
    # this arm's club targets, and its per-carry rushing factors are kept (rushing has no cross-player identity).
    inc_seed = seed + 99 if incumbent_seed is None else incumbent_seed
    _inc_dk, inc_worlds, inc_eff = CR.efficiency_worlds(sd, rows_by_key, int_rate, inc_seed)
    INC = {k: np.asarray(v, dtype=float) for k, v in inc_worlds.items()}

    out_lines = {k: np.zeros((n, len(WORLD_FIELDS))) for k in keys}
    account = {'anchor': anchor, 'clubs': {}, 'NOT_REPRESENTED': NOT_REPRESENTED}
    events = {c: {f: [0.0] * n for f in EVENT_FIELDS} for c in clubs}

    for c in clubs:
        opp = away if c == home else home
        mem = [k for k in keys if _club(k) == c]
        qbs = [k for k in mem if rows_by_key[k].get('position') == 'QB']
        recs = [k for k in mem if k not in qbs]
        if not qbs:
            raise _Refuse('EVENT_WORLDS_NO_QUARTERBACK', f'{c}: no QB in the drawn pool', club=c)
        acc = {'qbs': qbs, 'n_receivers': len(recs)}
        # ---- 1. catch yards
        cv_ry = [(rows_by_key[k].get('conditional_volume') or {}).get('rec_yards') for k in recs]
        cv_rc = [(rows_by_key[k].get('conditional_volume') or {}).get('receptions') for k in recs]
        ok = [(y, r) for y, r in zip(cv_ry, cv_rc) if _ratio(y, r) is not None]
        club_ypc = (sum(y for y, _ in ok) / sum(r for _, r in ok)) if ok and sum(r for _, r in ok) > 0 else None
        if club_ypc is None:
            raise _Refuse('EVENT_WORLDS_NO_YARDS_PER_CATCH', f'{c}: no receiver carries conditional rec_yards and '
                          f'receptions, so a catch cannot be given yards', club=c)
        U = np.zeros(n)
        u = {}
        ypc_src = {}
        for k, y, r in zip(recs, cv_ry, cv_rc):
            tg, rc, ry = S[k][:, _I['targets']], S[k][:, _I['receptions']], S[k][:, _I['rec_yards']]
            ypc = _ratio(y, r)
            ypc_src[k] = 'PLAYER' if ypc is not None else 'CLUB_FALLBACK'
            ypc = ypc if ypc is not None else club_ypc
            ypt_sim = ry.sum() / tg.sum() if tg.sum() > 0 else 0.0
            if ypt_sim > 0:
                g = np.where(tg > 0, ry / np.where(tg > 0, tg, 1.0), 0.0) / ypt_sim
            else:
                g = np.ones(n)
            u[k] = rc * ypc * g
            U += u[k]
        if anchor == ANCHOR_QB:
            target = float(sum(INC[q][:, _I['pass_yards']].mean() for q in qbs))
        else:
            target = float(sum(INC[k][:, _I['rec_yards']].mean() for k in recs))
        if U.mean() <= 0:
            raise _Refuse('EVENT_WORLDS_NO_CATCH_YARDS', f'{c}: simulated catch yards have zero mean', club=c)
        F = target / U.mean()
        acc.update({'club_pass_yards_target': round(target, 3), 'club_factor': round(F, 5),
                    'incumbent_qb_pass_yards_mean': round(float(sum(INC[q][:, _I['pass_yards']].mean()
                                                                    for q in qbs)), 3),
                    'incumbent_receiver_yards_sum_mean': round(float(sum(INC[k][:, _I['rec_yards']].mean()
                                                                         for k in recs)), 3),
                    'club_yards_per_catch_fallback': round(club_ypc, 4),
                    'receivers_on_club_ypc_fallback': sorted(k for k, s in ypc_src.items() if s != 'PLAYER')})
        for k in recs:
            out_lines[k][:, _I['rec_yards']] = F * u[k]
        Y = F * U
        # ---- 3. QB yards = sum of receivers' yards, shared by attempts
        A = np.array([S[q][:, _I['pass_att']] for q in qbs])        # [q, w]
        At = A.sum(0)
        no_passer = int(((Y > 0) & (At <= 0)).sum())
        for i, q in enumerate(qbs):
            share = np.where(At > 0, A[i] / np.where(At > 0, At, 1.0), 0.0)
            out_lines[q][:, _I['pass_yards']] = Y * share
        acc['worlds_pass_yards_with_no_represented_passer'] = no_passer

        # ---- 4. TDs on catches and carries
        rng_p, rng_r, rng_q = _rng(seed, c, 'pass_td'), _rng(seed, c, 'rush_td'), _rng(seed, c, 'qb_credit')
        tpc = []
        for k in recs:
            r = rows_by_key[k]
            tpc.append(_ratio((r.get('td') or {}).get('rec_td'), r.get('receptions')) or 0.0)
        tpr = []
        for k in mem:
            r = rows_by_key[k]
            tpr.append(_ratio((r.get('td') or {}).get('rush_td'), r.get('carries')) or 0.0)
        raw_qb_ptd = sum(S[q][:, _I['pass_td']] for q in qbs)
        raw_rec_td = sum(S[k][:, _I['rec_td']] for k in recs) if recs else np.zeros(n)
        raw_rush_td = sum(S[k][:, _I['rush_td']] for k in mem)
        club_td = np.array([float(t) for _, t in csw[c]])
        n_pass = np.maximum(raw_qb_ptd, raw_rec_td)
        n_rush = club_td - n_pass
        short = n_rush < raw_rush_td
        n_rush = np.where(short, raw_rush_td, n_rush)
        acc.update({'worlds_raw_qb_pass_td_ne_receiver_td': int((raw_qb_ptd != raw_rec_td).sum()),
                    'worlds_raw_club_td_ne_player_td': int((club_td != raw_qb_ptd + raw_rush_td).sum()),
                    'worlds_club_td_below_player_td': int(short.sum())})
        un_p = un_r = un_noqb = 0
        for w in range(n):
            caps = [int(S[k][w, _I['receptions']]) for k in recs]
            got, up = _place(n_pass[w], caps, tpc, rng_p)
            placed = sum(got)
            aw = [float(A[i, w]) for i in range(len(qbs))]
            if placed and sum(aw) <= 0:
                un_noqb += placed
                got, placed = [0] * len(recs), 0
            for k, g_ in zip(recs, got):
                out_lines[k][w, _I['rec_td']] = g_
            if placed:
                for q, g_ in zip(qbs, _split_count(placed, aw, rng_q)):
                    out_lines[q][w, _I['pass_td']] = g_
            un_p += up
            caps = [int(S[k][w, _I['carries']]) for k in mem]
            got, ur = _place(n_rush[w], caps, tpr, rng_r)
            for k, g_ in zip(mem, got):
                out_lines[k][w, _I['rush_td']] = g_
            un_r += ur
        acc.update({'pass_td_unplaced_no_catch': un_p, 'rush_td_unplaced_no_carry': un_r,
                    'pass_td_dropped_no_represented_passer': un_noqb})

        # ---- volumes as drawn; rushing yards = incumbent per-carry anchored, zero without a carry
        zeroed = 0
        for k in mem:
            for f in ('pass_att', 'carries', 'targets', 'receptions'):
                out_lines[k][:, _I[f]] = S[k][:, _I[f]]
            ry = INC[k][:, _I['rush_yards']]
            car = S[k][:, _I['carries']]
            zeroed += int(((car == 0) & (ry != 0)).sum())
            out_lines[k][:, _I['rush_yards']] = np.where(car > 0, ry, 0.0)
        acc['rush_yard_cells_zeroed_no_carry'] = zeroed

        # ---- 5. INTs thinned from the opposing DST's takeaways
        take = np.array([float(t[1]) for t in dcomp[dst_key[opp]]])
        want = int_rate * float(At.mean())
        q_raw = float(want / take.mean()) if take.mean() > 0 else float('inf')
        qv = min(1.0, q_raw)
        rng_i = _rng(seed, c, 'int')
        capped = 0
        ints_c = np.zeros(n)
        for w in range(n):
            k_int = _binom(int(take[w]), qv, rng_i)
            if k_int > At[w]:
                capped += k_int - int(At[w])
                k_int = int(At[w])
            ints_c[w] = k_int
            if k_int:
                for q, g_ in zip(qbs, _split_count(k_int, [float(A[i, w]) for i in range(len(qbs))], rng_i)):
                    out_lines[q][w, len(STAT_FIELDS)] = g_
        acc.update({'int_target_mean': round(want, 4), 'opp_takeaways_mean': round(float(take.mean()), 4),
                    'int_share_of_opp_takeaways_q': round(q_raw, 5), 'q_capped_at_1': bool(q_raw > 1.0),
                    'ints_capped_at_attempts': capped, 'int_mean': round(float(ints_c.mean()), 4),
                    'implied_fumble_takeaways_mean': round(float((take - ints_c).mean()), 4)})
        for w in range(n):
            events[c]['pass_td'][w] = float(sum(out_lines[q][w, _I['pass_td']] for q in qbs))
            events[c]['rush_td'][w] = float(sum(out_lines[k][w, _I['rush_td']] for k in mem))
            events[c]['off_td'][w] = events[c]['pass_td'][w] + events[c]['rush_td'][w]
        account['clubs'][c] = acc

    # ---- 6. kicking events, club points as event sums, DST from components
    kick_key = {}
    for k, v in (art.get('kickers') or {}).items():
        if (v or {}).get('ROLE') != 'NOT_THE_CLUB_KICKER':
            kick_key[_club(k)] = k
    raw_pts = {home: [p[0] for p in world_pts['points']], away: [p[1] for p in world_pts['points']]}
    kdk = {}
    for c in clubs:
        mix, rates = _kicker_inputs(c, kicker_inputs)
        rk = _rng(seed, c, 'kicker')
        dks = []
        for w in range(n):
            dk, d = kicker_line(raw_pts[c][w], events[c]['off_td'][w], mix, rates, rk)
            dks.append(float(dk))
            for f in ('xp_att', 'xp_made', 'tp_att', 'tp_made', 'fg_made', 'fg_0_39_made', 'fg_40_49_made',
                      'fg_50_plus_made'):
                events[c][f][w] = float(d.get(f, 0))
            comp = dcomp[dst_key[c]][w]
            events[c]['def_td'][w] = float(comp[2])
            events[c]['safety'][w] = float(comp[3])
            e = events[c]
            e['points'][w] = (POINTS_PER['td'] * (e['off_td'][w] + e['def_td'][w]) + POINTS_PER['xp'] * e['xp_made'][w]
                              + POINTS_PER['tp'] * e['tp_made'][w] + POINTS_PER['fg'] * e['fg_made'][w]
                              + POINTS_PER['safety'] * e['safety'][w])
        kdk[c] = dks
    draws = {}
    for k in keys:
        draws[k] = [float(CR.dk_from_stats(*row)) for row in out_lines[k].tolist()]
    for k, v in (art.get('draws') or {}).items():
        if k in draws:
            continue
        c = _club(k)
        if k == kick_key.get(c):
            draws[k] = kdk[c]
        elif k in (art.get('kickers') or {}):
            draws[k] = [0.0] * n                    # a club's other K row: zero opportunity, as in the incumbent
        elif k == dst_key.get(c):
            opp = away if c == home else home
            draws[k] = [float(_dst_dk(events[opp]['points'][w], dcomp[k][w])) for w in range(n)]
        else:
            raise _Refuse('EVENT_WORLDS_UNKNOWN_DRAW', f'{k} is neither a drawn skill player, a kicker nor a DST')
    band_changed = {}
    for c in clubs:
        opp = away if c == home else home
        band_changed[dst_key[c]] = int(sum(_band(raw_pts[opp][w]) != _band(events[opp]['points'][w])
                                           for w in range(n)))
    account['dst_band_changed_worlds'] = band_changed
    account['kicker_keys'] = kick_key
    account['dst_keys'] = dst_key
    account['incumbent_efficiency'] = {'factors': inc_eff['factors'], 'not_anchorable': inc_eff['not_anchorable']}
    pts_ev = [(events[home]['points'][w], events[away]['points'][w]) for w in range(n)]
    return {
        'ARM': ARM, 'spec_version': SPEC_VERSION, 'n_worlds': n, 'home': home, 'away': away, 'seed': seed,
        'stat_worlds': {k: [tuple(r) for r in out_lines[k].tolist()] for k in keys},
        'draws': draws,
        'world_points': {'home': home, 'away': away, 'points': pts_ev},
        'club_scoring_worlds': {c: [(events[c]['points'][w], events[c]['off_td'][w]) for w in range(n)]
                                for c in clubs},
        'dst_components': {k: [list(x) for x in v] for k, v in dcomp.items()},
        'scoring_events': {c: {f: events[c][f] for f in EVENT_FIELDS} for c in clubs},
        'qb_interceptions': {k: [r[len(STAT_FIELDS)] for r in out_lines[k].tolist()] for k in keys
                             if rows_by_key[k].get('position') == 'QB'},
        'account': account,
    }


def publish(result: dict, out_dir, tag: str, *, game_id: str, projection_sha: str = None, state_path=None,
            extra: dict = None) -> dict:
    """Write the arm's published worlds in the incumbent's format (so world_accounting_check reads them)."""
    import shutil
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    wpath = out_dir / f'SHOWDOWN_{tag}_WORLDS.npz'
    CR._write_worlds(wpath, result['stat_worlds'], {game_id: {'world_points': result['world_points']}},
                     projection_sha)
    doc = {
        'ARTIFACT': 'SHOWDOWN_SLATE_DRAWS', 'ARM': ARM, 'spec_version': SPEC_VERSION, 'tag': tag,
        'game_id': game_id, 'home': result['home'], 'away': result['away'], 'n_sims': result['n_worlds'],
        'seed': result['seed'], 'SHADOW_ONLY': 'research arm; not consumed by any production path',
        'projection_sha256': projection_sha,
        'world_points': result['world_points'], 'club_scoring_worlds': result['club_scoring_worlds'],
        'dst_components': result['dst_components'], 'scoring_events': result['scoring_events'],
        'EVENT_FIELDS': list(EVENT_FIELDS), 'qb_interceptions': result['qb_interceptions'],
        'account': result['account'], **(extra or {}),
        'draws': result['draws'],
    }
    dpath = out_dir / f'SHOWDOWN_{tag}_DRAWS.json'
    dpath.write_text(json.dumps(doc, separators=(',', ':'), default=str))
    if state_path is not None:
        shutil.copyfile(state_path, out_dir / pathlib.Path(state_path).name)
    return {'worlds': str(wpath), 'draws': str(dpath)}


def event_checks(scenario_dir) -> dict:
    """Accounting laws world_accounting_check does not carry, on PUBLISHED files. A law whose events the
    artifact does not store is NOT_MEASURABLE (never a pass)."""
    import numpy as np
    from nfl.tools import world_accounting_check as WAC
    meta, S, pts, doc, _state, _files = WAC.load(pathlib.Path(scenario_dir))
    F = {f: i for i, f in enumerate(meta['fields'])}
    keys = meta['keys']
    club = np.array([_club(k) for k in keys])
    out = {}

    def put(name, mask, detail, cells=None):
        if mask is None:
            out[name] = {'state': 'NOT_MEASURABLE', 'detail': detail}
            return
        out[name] = {'violations': int(mask.sum()), 'of': int(mask.size), 'detail': detail,
                     **({'player_world_cells': int(cells)} if cells is not None else {})}

    rec, rectd = S[:, :, F['receptions']], S[:, :, F['rec_td']]
    car, rtd, ryd = S[:, :, F['carries']], S[:, :, F['rush_td']], S[:, :, F['rush_yards']]
    tol = 0.5 / meta['yard_scale']
    put('REC_TD_LE_RECEPTIONS', (rectd > rec).any(0), 'any player with more receiving TDs than receptions',
        (rectd > rec).sum())
    put('RUSH_TD_LE_CARRIES', (rtd > car).any(0), 'any player with more rushing TDs than carries', (rtd > car).sum())
    put('RUSH_YDS_WITHOUT_CARRY', ((np.abs(ryd) > tol) & (car == 0)).any(0),
        'any player with rushing yards and no carry', ((np.abs(ryd) > tol) & (car == 0)).sum())
    g = meta['games'][0]
    ev = doc.get('scoring_events')
    csw = doc.get('club_scoring_worlds') or {}
    for c, opp, col in ((g['home'], g['away'], 0), (g['away'], g['home'], 1)):
        m = club == c
        ptd = S[m, :, F['pass_td']].sum(0) + S[m, :, F['rush_td']].sum(0)
        if c in csw:
            ctd = np.array([float(t) for _, t in csw[c]])
            put(f'{c}:CLUB_TD_EQ_PLAYER_TD', ctd != ptd, 'club offensive TDs (scoring worlds) vs TDs on player lines')
        if ev and c in ev:
            e = {f: np.asarray(v, dtype=float) for f, v in ev[c].items()}
            put(f'{c}:EVENT_TD_EQ_PLAYER_TD', e['off_td'] != ptd, 'offensive TDs in the events vs on player lines')
            s = (POINTS_PER['td'] * (e['off_td'] + e['def_td']) + POINTS_PER['xp'] * e['xp_made']
                 + POINTS_PER['tp'] * e['tp_made'] + POINTS_PER['fg'] * e['fg_made'] + POINTS_PER['safety'] * e['safety'])
            put(f'{c}:POINTS_EQ_EVENT_SUM', np.abs(pts[0, :, col] - s) > 1e-3,
                'published club points vs 6(TD+defTD)+XP+2*2pt+3*FG+2*safety')
            kk = next((k for k in doc.get('account', {}).get('kicker_keys', {}).values() if _club(k) == c), None)
            if kk:
                kd = np.asarray(doc['draws'][kk], dtype=float)
                rec_k = e['xp_made'] + 3 * e['fg_0_39_made'] + 4 * e['fg_40_49_made'] + 5 * e['fg_50_plus_made']
                put(f'{c}:KICKER_DK_FROM_EVENTS', np.abs(kd - rec_k) > 1e-6, f'{kk} DK vs XP + 3/4/5 by FG band')
                put(f'{c}:FG_BANDS_SUM', e['fg_0_39_made'] + e['fg_40_49_made'] + e['fg_50_plus_made'] != e['fg_made'],
                    'FG made by band sums to FG made')
        else:
            put(f'{c}:POINTS_EQ_EVENT_SUM', None, 'the artifact stores no per-world scoring events')
            put(f'{c}:KICKER_DK_FROM_EVENTS', None, 'the artifact stores no per-world XP made / FG bands')
        dk = next((k for k in doc.get('dst_components', {}) if k.endswith('|' + c)), None)
        if dk and dk in doc.get('draws', {}):
            comp = doc['dst_components'][dk]
            pa = pts[0, :, 1 - col]
            rec_d = np.array([_dst_dk(float(pa[w]), comp[w]) for w in range(len(comp))])
            put(f'{c}:DST_DK_FROM_COMPONENTS', np.abs(np.asarray(doc['draws'][dk], float) - rec_d) > 1e-3,
                f'{dk} DK vs tier(published points allowed) + sacks + 2 takeaways + 6 def TD + 2 safeties')
    return {'ARTIFACT': 'EVENT_ACCOUNTING_CHECK', 'spec_version': SPEC_VERSION, 'scenario_dir': str(scenario_dir),
            'VIOLATED': {k: v['violations'] for k, v in out.items() if v.get('violations')},
            'NOT_MEASURABLE': sorted(k for k, v in out.items() if v.get('state') == 'NOT_MEASURABLE'),
            'checks': out}
