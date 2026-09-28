#!/usr/bin/env python3.12
"""Usage-first allocation: the club total is DERIVED from the players, not imposed on them.

THE DEFECT THIS REPLACES

The simulator drew a club rushing-yard total and split it across the backs with a Dirichlet. That
makes teammates zero-sum by construction: whatever one back gets, the other cannot. Measured football
does not behave that way. The two pregame-ranked backs correlate at +0.0739 in carries, and BOTH rise
with the club total (+0.63 and +0.43), while the simulator produced -0.249 in fantasy points. Adding
measured share dispersion made it worse, because a Dirichlet moves work between teammates rather than
creating it.

WHAT THE MEASUREMENT SHOWS, AND WHY IT IS AN ARCHITECTURE PROBLEM

Decomposing the observed teammate covariance of +1.51 carries:

    shared club total contributes   E[s1] E[s2] Var(T)  = +5.38
    share competition contributes   E[T]^2 cov(s1, s2)  = -3.87
                                                          ------
                                                          +1.51

So competition is real and the shared total dominates it. A fixed-total simplex keeps only the second
term and throws away the first, which is why it cannot reach a positive answer with any concentration.

The second measurement is the one that decides the architecture. Of the variance in yards per carry,
63% is PLAYER-level rather than club-level (80% for yards per target). The old structure attributed
essentially all of it to the club -- one efficiency draw per club-game, then a zero-sum split of a
fixed club yardage -- so it had the decomposition almost exactly backwards.

THE HIERARCHY

    game state -> team play volume -> pass/rush share -> role-dependent opportunity
               -> per-player efficiency -> club yardage as the SUM

Volume still reconciles exactly to the drawn club attempts, because attempts genuinely are shared: a
carry given to one back is not given to another. Yardage no longer does, because it never should
have: each player's yards are his own carries times his own efficiency, and the club's rushing yards
are whatever those add up to. The identity becomes "club yards equal the sum of player yards", which
is exact and derived rather than exact and imposed.

A QUARTERBACK'S PASSING YARDS BECOME AN IDENTITY

Under this structure a quarterback's passing yards are the sum of his receivers' receiving yards,
which is what they are in football. The old structure drew club passing yards first and then split
them, so the quarterback and his receivers were tied to a number neither of them produced.
"""
from __future__ import annotations

import collections
import json
import math
import pathlib
import random
import statistics
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

PG = _REPO / 'nfl/warehouse/PLAYER_GAME.json'
RH = _REPO / 'nfl/warehouse/ROLE_HISTORY.json'
OUT = _REPO / 'nfl/sim/USAGE_MODEL.json'
RANK_MEASURE = {'QB': 'pass_attempts', 'RB': 'carries', 'WR': 'targets', 'TE': 'targets'}
BOOT = 400


def _rows(p):
    a = json.loads(p.read_text())
    r = a['rows']
    return r if isinstance(r, list) else list(r.values())


def _efficiency_split(club_games, opp_field, yd_field, min_player, min_club):
    """Split efficiency variance into a club-game component and a player component."""
    between, within = [], []
    for ps in club_games:
        q = [p for p in ps
             if isinstance(p.get(opp_field), (int, float)) and p[opp_field] >= min_player
             and isinstance(p.get(yd_field), (int, float))]
        tot_o = sum(p[opp_field] for p in q)
        tot_y = sum(p[yd_field] for p in q)
        if len(q) < 2 or tot_o < min_club:
            continue
        club = tot_y / tot_o
        between.append(club)
        for p in q:
            within.append(p[yd_field] / p[opp_field] - club)
    if len(between) < 200:
        return {'state': 'NOT_IDENTIFIED_TOO_FEW_CLUB_GAMES', 'n': len(between)}
    vb, vw = statistics.pvariance(between), statistics.pvariance(within)
    return {
        'state': 'MEASURED',
        'n_club_games': len(between), 'n_player_games': len(within),
        'club_mean': round(statistics.fmean(between), 4),
        'club_sd': round(statistics.stdev(between), 4),
        'player_deviation_mean': round(statistics.fmean(within), 4),
        'player_deviation_sd': round(statistics.stdev(within), 4),
        'club_variance': round(vb, 4), 'player_variance': round(vw, 4),
        'player_share_of_variance': round(vw / (vb + vw), 4),
        'empirical_club': [round(x, 4) for x in sorted(between)],
        'empirical_player_deviation': [round(x, 4) for x in sorted(within)],
        'READING': ('the player share is what the old structure got backwards. One club efficiency '
                    'draw shared by everyone attributes all of this to the club.'),
    }


def _teammate_decomposition(club_games, rank, pos, field, min_club):
    """Split the observed teammate covariance into a shared-total part and a competition part."""
    a1, a2, tot = [], [], []
    for ps in club_games:
        slot, T = {}, 0.0
        for p in ps:
            v = p.get(field)
            if isinstance(v, (int, float)):
                T += float(v)
            pr = rank.get((int(p['season']), int(p['week']), p['player_id']))
            if pr and pr[0] == pos and pr[1] in (1, 2) and isinstance(v, (int, float)):
                slot[pr[1]] = float(v)
        if 1 in slot and 2 in slot and T >= min_club:
            a1.append(slot[1])
            a2.append(slot[2])
            tot.append(T)
    if len(a1) < 200:
        return {'state': 'NOT_IDENTIFIED_TOO_FEW', 'n': len(a1)}
    n = len(a1)
    m1, m2, mT = statistics.fmean(a1), statistics.fmean(a2), statistics.fmean(tot)
    v1, v2, vT = statistics.pvariance(a1), statistics.pvariance(a2), statistics.pvariance(tot)
    cov = sum((x - m1) * (y - m2) for x, y in zip(a1, a2)) / n
    r12 = cov / math.sqrt(v1 * v2) if v1 > 0 and v2 > 0 else None
    s1, s2 = m1 / mT, m2 / mT
    from_total = s1 * s2 * vT
    from_shares = cov - from_total
    cov_shares = from_shares / (mT ** 2) if mT else None
    # a Dirichlet over shares implies cov(s_i, s_j) = -w_i w_j / (alpha + 1), so alpha is identified
    alpha = None
    if cov_shares is not None and cov_shares < 0:
        alpha = (-(s1 * s2) / cov_shares) - 1.0
    rng = random.Random(97)
    boots = []
    for _ in range(BOOT):
        idxs = [rng.randrange(n) for _ in range(n)]
        b1 = [a1[i] for i in idxs]
        b2 = [a2[i] for i in idxs]
        bm1, bm2 = statistics.fmean(b1), statistics.fmean(b2)
        bv1, bv2 = statistics.pvariance(b1), statistics.pvariance(b2)
        if bv1 <= 0 or bv2 <= 0:
            continue
        bc = sum((x - bm1) * (y - bm2) for x, y in zip(b1, b2)) / n
        boots.append(bc / math.sqrt(bv1 * bv2))
    boots.sort()
    return {
        'state': 'MEASURED', 'n_club_games': n,
        'mean_rank1': round(m1, 3), 'mean_rank2': round(m2, 3), 'mean_club_total': round(mT, 3),
        'corr_rank1_rank2': round(r12, 4) if r12 is not None else None,
        'ci95_corr': ([round(boots[int(0.025 * len(boots))], 4),
                       round(boots[int(0.975 * len(boots))], 4)] if len(boots) > 40 else None),
        'covariance': round(cov, 4),
        'covariance_from_shared_total': round(from_total, 4),
        'covariance_from_share_competition': round(from_shares, 4),
        'implied_share_covariance': round(cov_shares, 6) if cov_shares is not None else None,
        'implied_dirichlet_concentration': round(alpha, 3) if alpha else None,
        'share_rank1': round(s1, 4), 'share_rank2': round(s2, 4),
        'DECOMPOSITION': ('observed covariance = E[s1] E[s2] Var(total) + E[total]^2 cov(s1, s2). '
                          'A fixed-total simplex keeps only the second term, which is why no '
                          'concentration can reproduce a positive teammate correlation.'),
    }


def ranked_group_share_of_club(club_games, ranked) -> dict:
    """What fraction of a club's opportunity the DEPTH-RANKED players actually take.

    THE DENOMINATOR DEFECT THIS EXISTS TO CLOSE. ROLE_HISTORY's `share_of_club` is, for carries and
    targets, a share of the RANKED GROUP rather than of the club. The correlation replay fed those
    numbers in as club shares, so the two ranked backs were handed 0.7397 and 0.2331 -- 97% of the
    club's carries between two players, against a measured 0.561 and 0.187. Two players splitting a
    fixed pot almost entirely between themselves are forced to be zero-sum, and that, not the
    allocation architecture, was the main reason the simulated backs came out at -0.24.

    This is the same share-of-group-versus-share-of-club error the projection work hit once before in
    the depth curve. It is worth naming twice.
    """
    out = {}
    for pos, field in (('RB', 'carries'), ('WR', 'targets'), ('TE', 'targets'),
                       ('QB', 'pass_attempts')):
        fr = []
        for ps in club_games:
            tot = sum(float(p[field]) for p in ps if isinstance(p.get(field), (int, float)))
            if tot < 10:
                continue
            rk = 0.0
            for p in ps:
                e = ranked.get((int(p['season']), int(p['week']), p['player_id']))
                v = p.get(field)
                if e and e[0] == pos and isinstance(v, (int, float)):
                    rk += float(v)
            fr.append(rk / tot)
        if len(fr) < 200:
            out[f'{pos}_{field}'] = {'state': 'NOT_IDENTIFIED', 'n': len(fr)}
            continue
        out[f'{pos}_{field}'] = {
            'state': 'MEASURED', 'mean': round(statistics.fmean(fr), 4),
            'median': round(statistics.median(fr), 4), 'sd': round(statistics.stdev(fr), 4),
            'n': len(fr),
            'USE': ('multiply a ROLE_HISTORY share by this to get a share OF THE CLUB; the '
                    'remainder belongs to unranked players and must go to the explicit '
                    'unallocated bucket, never be renormalised onto the ranked players'),
        }
    return out


def build() -> Outcome:
    if not PG.exists() or not RH.exists():
        return Outcome.blocked('USAGE_INPUTS_ABSENT', 'player-game or role-history missing',
                               cause=Cause.DATA)
    pg, rh = _rows(PG), _rows(RH)
    rank = {}
    for r in rh:
        if RANK_MEASURE.get(r.get('position')) != r.get('measure'):
            continue
        if isinstance(r.get('depth_rank'), (int, float)):
            rank[(int(r['season']), int(r['week']), r['player_id'])] = (r['position'],
                                                                       int(r['depth_rank']))
    by_club = collections.defaultdict(list)
    for r in pg:
        by_club[(r['game_id'], r['club'])].append(r)
    club_games = list(by_club.values())

    art = {
        'ARTIFACT': 'USAGE_MODEL',
        'REPLACES': ('the fixed-club-total Dirichlet split of yardage in nfl/sim/game.py, which '
                     'made teammates zero-sum by construction'),
        'HIERARCHY': ['game state', 'team play volume', 'pass/rush share',
                      'role-dependent opportunity', 'per-player efficiency',
                      'club yardage as the SUM'],
        'rushing_efficiency': _efficiency_split(club_games, 'carries', 'rushing_yards', 5, 15),
        'receiving_efficiency': _efficiency_split(club_games, 'targets', 'receiving_yards', 3, 15),
        'teammate_backs': _teammate_decomposition(club_games, rank, 'RB', 'carries', 10),
        'teammate_receivers': _teammate_decomposition(club_games, rank, 'WR', 'targets', 10),
        'teammate_tight_ends': _teammate_decomposition(club_games, rank, 'TE', 'targets', 10),
        'ranked_group_share_of_club': ranked_group_share_of_club(club_games, rank),
        'WHAT_STAYS_ZERO_SUM_AND_WHY': (
            'attempts, carries and targets genuinely are shared -- a carry given to one back is not '
            'given to another -- so volume still reconciles exactly to the drawn club total. '
            'Touchdowns are shared for the same reason. YARDAGE is not shared: a back\'s yards are '
            'his own carries times his own efficiency, so club yardage is derived as the sum.'),
    }
    OUT.write_text(json.dumps(art, indent=2))
    bad = [k for k in ('rushing_efficiency', 'receiving_efficiency', 'teammate_backs')
           if art[k].get('state') != 'MEASURED']
    if bad:
        return Outcome.fail('USAGE_MODEL_NOT_IDENTIFIED', f'{bad} could not be measured',
                            **{k: art[k] for k in bad})
    return Outcome.ok('USAGE_MODEL_MEASURED', value={
        k: ({kk: vv for kk, vv in v.items() if not kk.startswith('empirical')}
            if isinstance(v, dict) else v)
        for k, v in art.items()})


if __name__ == '__main__':
    o = build()
    print(o.state.value, o.code)
    v = o.value if o.value else o.evidence
    for k in ('rushing_efficiency', 'receiving_efficiency'):
        d = v.get(k, {})
        if d.get('state') == 'MEASURED':
            print(f"  {k:22s} club sd {d['club_sd']:.3f}  player dev sd "
                  f"{d['player_deviation_sd']:.3f}  PLAYER SHARE OF VARIANCE "
                  f"{d['player_share_of_variance']:.3f}")
    for k, d in (v.get('ranked_group_share_of_club') or {}).items():
        if d.get('state') == 'MEASURED':
            print(f"  ranked share of club {k:22s} {d['mean']:.4f} (sd {d['sd']:.4f})")
    for k in ('teammate_backs', 'teammate_receivers', 'teammate_tight_ends'):
        d = v.get(k, {})
        if d.get('state') == 'MEASURED':
            print(f"  {k:22s} corr {d['corr_rank1_rank2']:+.4f} ci{d['ci95_corr']}  "
                  f"cov {d['covariance']:+.3f} = total {d['covariance_from_shared_total']:+.3f} "
                  f"+ competition {d['covariance_from_share_competition']:+.3f}  "
                  f"alpha {d['implied_dirichlet_concentration']}")
    raise SystemExit(0 if o.state.value == 'PASS' else 1)
