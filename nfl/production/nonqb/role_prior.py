"""R6: a role-conditional class-share prior. Point-in-time, empirically shrunk.

TWO DEFECTS THIS ADDRESSES, BOTH MEASURED.

1. THE WEIGHT IS ROLE-BLIND WHERE IT HAS NO HISTORY.
   `p4c_params.class_point_forecast` falls back to the POSITIONAL MEAN share
   for a player with no prior appeared games -- 0.1253 for every WR, whether
   he is a team's second option or its ninth. Historical realised target share
   by point-in-time depth tier, 2020-2025: WR1 22.7%, WR2 18.3%, WR3 13.3%,
   WR4+ 6.1%. A single positional mean is a 3.7:1 spread collapsed to 1:1.

2. THE PARTICIPATION PRIOR IS TOO FLAT, AND IT IS THE WRONG QUANTITY.
   `participation_prior.share_prior` is a PASS-SNAP participation rate: for
   LA's top four it reads 0.787 / 0.740 / 0.736 / 0.725, a top-to-fringe ratio
   of 1.39:1. Historical snap share by tier is 81.5% / 74.1% / 59.7% / 32.7%,
   a ratio of 2.5:1 -- so it is too flat even as a snap quantity. It is then
   used to allocate TARGETS, where the realised ratio is 3.7:1. The layer's own
   warning already says pass-snap participation is "an upper bound on routes
   run"; this quantifies by how much.

WHAT IS AND IS NOT DONE HERE.

A player's own history still governs him wherever he has any. This changes
what happens in the ABSENCE of history, and how strongly a short history is
trusted -- nothing else. No player is named, no team is special-cased, and no
constant is chosen: the shrinkage weight is `n / (n + k)` with `k` estimated
from the panel as the ratio of within-player to between-player variance of the
class share (empirical Bayes). Measured: WR 0.87, TE 0.78, RB-targets 1.54,
RB-carries 0.74.

TIER IS POINT-IN-TIME AND NEVER SEES ITS OWN GAME. It is the rank of a
player's TRAILING mean snap share within his team and position, computed from
strictly earlier weeks. Where a player has no trailing history the captured
depth chart supplies the rank instead; where neither exists he is placed in the
lowest tier and that is recorded rather than assumed away.
"""
from __future__ import annotations

import collections
import statistics

from sportsplatform.governance.outcome import Cause, Outcome

SPEC_VERSION = 'role-prior-tier-conditional-r6'

# How many trailing appeared games form the tier signal. Not a fitted number:
# it is the same window the participation prior already uses.
TRAIL = 8
MAX_TIER = 4          # tiers 1..3 then 4+ , matching the historical table


def _tier_label(pos, t):
    return f'{pos}{min(int(t), MAX_TIER)}'


def build(panel, cls_share, positions, ordinal_cut) -> Outcome:
    """Tier means and the shrinkage constant, from rows strictly earlier than
    `ordinal_cut`. Returns everything the caller needs to price a player."""
    rows = [r for r in panel
            if r.get('position') in positions and r.get('ord', 0) < ordinal_cut]
    if not rows:
        return Outcome.blocked(
            'ROLE_PRIOR_NO_HISTORY',
            f'no {cls_share} history earlier than {ordinal_cut}; a role prior '
            f'over nothing is not one', cause=Cause.DATA)
    rows.sort(key=lambda r: (r['ord'], r['team'], r['gsis_id']))

    # --- point-in-time tier, rebuilt the same way for every historical week
    trail = collections.defaultdict(list)
    by_ord = collections.defaultdict(list)
    for r in rows:
        by_ord[r['ord']].append(r)
    tier = {}
    for o in sorted(by_ord):
        grp = collections.defaultdict(list)
        for r in by_ord[o]:
            h = trail.get(r['gsis_id'])
            r['_trail'] = statistics.mean(h[-TRAIL:]) if h else None
            grp[(r['team'], r['position'])].append(r)
        for _k, rs in grp.items():
            known = sorted([x for x in rs if x['_trail'] is not None],
                           key=lambda x: -x['_trail'])
            for i, x in enumerate(known):
                tier[(x['ord'], x['gsis_id'])] = i + 1
            for x in rs:
                if x['_trail'] is None:
                    tier[(x['ord'], x['gsis_id'])] = None
        for r in by_ord[o]:
            s = r.get('snap_share')
            if s is not None and r.get('appeared'):
                trail[r['gsis_id']].append(s)

    # --- tier means of the class share, appeared rows only
    tv = collections.defaultdict(list)
    per_player = collections.defaultdict(list)
    for r in rows:
        if not r.get('appeared'):
            continue
        v = r.get(cls_share)
        if v is None:
            continue
        t = tier.get((r['ord'], r['gsis_id']))
        if t is not None:
            tv[_tier_label(r['position'], t)].append(v)
        per_player[(r['position'], r['gsis_id'])].append(v)
    tier_mean = {k: float(statistics.mean(v)) for k, v in tv.items()
                 if len(v) >= 50}
    if not tier_mean:
        return Outcome.blocked(
            'ROLE_PRIOR_TIERS_TOO_THIN',
            f'no tier reached 50 observations for {cls_share}',
            cause=Cause.DATA)

    # --- empirical-Bayes k, per position. NOT A CHOSEN NUMBER.
    k = {}
    for pos in positions:
        vals = [v for (p_, _pid), v in per_player.items()
                if p_ == pos and len(v) >= 4]
        if len(vals) < 30:
            continue
        within = statistics.mean(statistics.pvariance(v) for v in vals)
        between = statistics.pvariance([statistics.mean(v) for v in vals])
        if between > 0:
            k[pos] = float(within / between)
    if not k:
        return Outcome.blocked(
            'ROLE_PRIOR_SHRINKAGE_UNIDENTIFIED',
            'between-player variance is zero, so the shrinkage weight is not '
            'identified and would have to be chosen rather than estimated',
            cause=Cause.DATA)

    # trailing snap share at the cut, for pricing prospective players
    latest = {pid: statistics.mean(h[-TRAIL:]) for pid, h in trail.items() if h}
    return Outcome.ok(
        'ROLE_PRIOR_OK',
        value={'tier_mean': tier_mean, 'k': k, 'trailing_snap': latest,
               'n_history': {pid: len(v) for (_p, pid), v in
                             per_player.items()}},
        spec_version=SPEC_VERSION, cls_share=cls_share,
        ordinal_cut=ordinal_cut, n_rows=len(rows),
        tier_means={kk: round(vv, 5) for kk, vv in sorted(tier_mean.items())},
        shrinkage_k={kk: round(vv, 3) for kk, vv in sorted(k.items())},
        note='k is within/between player variance of the class share; it is '
             'estimated, never chosen')


def assign_tiers(players, prior, depth_rank=None) -> dict:
    """Point-in-time tier for a prospective slate: trailing snap share where it
    exists, the captured depth chart otherwise."""
    trail = prior['trailing_snap']
    grp = collections.defaultdict(list)
    for q in players:
        grp[(q.get('team'), q.get('position'))].append(q)
    out, basis = {}, {}
    for _k, rs in grp.items():
        known = sorted([q for q in rs if trail.get(q['gsis_id']) is not None],
                       key=lambda q: -trail[q['gsis_id']])
        for i, q in enumerate(known):
            out[q['gsis_id']] = i + 1
            basis[q['gsis_id']] = 'trailing_snap_share'
        rest = [q for q in rs if q['gsis_id'] not in out]
        # THE DEPTH CHART IS THE FALLBACK, NOT A GUESS. It is captured, it is
        # point-in-time, and using it is the difference between placing a
        # rookie at his listed rank and placing him at the positional mean.
        ranked = []
        for q in rest:
            d = (depth_rank or {}).get(q['gsis_id'])
            ranked.append((d if d is not None else 99, q))
        ranked.sort(key=lambda x: x[0])
        start = len(known)
        for j, (d, q) in enumerate(ranked):
            out[q['gsis_id']] = start + j + 1
            basis[q['gsis_id']] = ('depth_chart' if d != 99
                                   else 'no_information_lowest_tier')
    return {'tier': out, 'basis': basis}


def weight(pid, position, own_ewma, n_own, tier, prior) -> float:
    """The R6 class weight: the player's own history shrunk toward his tier.

    With no history this is exactly the tier mean -- which is the repair. With
    a long history the shrinkage weight goes to one and the player's own value
    is returned unchanged, so R6 cannot overwrite an established starter with a
    positional average.
    """
    tm = prior['tier_mean'].get(_tier_label(position, tier))
    if tm is None:
        tm = statistics.mean(prior['tier_mean'].values()) if prior['tier_mean'] \
            else 0.0
    if own_ewma is None or not n_own:
        return float(tm)
    kk = prior['k'].get(position)
    if kk is None:
        kk = statistics.mean(prior['k'].values())
    w = n_own / (n_own + kk)
    return float(w * own_ewma + (1.0 - w) * tm)
