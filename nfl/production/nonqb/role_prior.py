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
strictly earlier weeks.

3. THE ROOM WAS ORDERED IN TWO PASSES, AND THE SECOND PASS COULD NEVER
   OVERTAKE THE FIRST. (R3, 2026-09-14. This is D4's P0-2.)

   `assign_tiers` used to sort everyone WITH a trailing snap share, then append
   everyone else starting at `start = len(known)`. A player the current depth
   chart ranks first, but who has no trailing history -- a rookie, a free agent,
   anyone whose history is at another club and outside the window -- was
   therefore placed below EVERY veteran with any history at all, however
   little. Replayed on week 1 of 2021-2024: 47 of 47 chart-rank-1 skill players
   with no trailing history landed below tier 1, 29 of them in tier 4+. Their
   assigned tiers imply a 0.0604 target share against a realised 0.1031, a 41%
   understatement, and because `weight` returns the tier mean EXACTLY at
   `n_own = 0`, for those players the tier was not a prior on a history -- it
   WAS the whole forecast.

   THE REPAIR IS STRUCTURAL, NOT A PROMOTION RULE. There is no ladder, no
   "rank 1 gets tier 1", and no player or team is named. The two passes are
   gone: every player in the room is placed on ONE continuous scale, an
   expected snap share

       score = w * own_trailing_snap + (1 - w) * anchor,   w = n / (n + k)

   where `anchor` is the empirically measured mean snap share of the tier his
   CURRENT depth listing puts him in, `n` is how many trailing observations he
   actually has, and `k` is the same empirical-Bayes within/between-player
   variance ratio the class prior already estimates -- here for snap share.
   Both `anchor` and `k` are estimated from the panel in `build`; neither is
   chosen. Current role evidence is the observation, history is the
   uncertainty information that shrinks it, and which of two players ends up
   higher is decided by that arithmetic and never by which list they were on.
   A player with no listing anchors on the deepest measured tier, which is the
   old behaviour made continuous rather than categorical.

   The pathology is then impossible by construction: there is no step at which
   one group is appended after another.
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

    # --- R3. THE SAME TWO ESTIMATES AGAIN, FOR SNAP SHARE.
    #
    # `assign_tiers` orders a room on expected snap share, so it needs an
    # anchor and a shrinkage constant in THAT quantity, not in the class share.
    # Both are measured here by the identical construction: the tier's own mean
    # snap share (appeared rows, same >=50 floor), and the within/between
    # player variance ratio. Nothing is chosen, and no value is carried over
    # from the class-share estimates -- a target share and a snap share are
    # different quantities and reusing one constant for both would be exactly
    # the silent-constant defect this module was written to end.
    sv = collections.defaultdict(list)
    snap_per_player = collections.defaultdict(list)
    for r in rows:
        if not r.get('appeared'):
            continue
        sn = r.get('snap_share')
        if sn is None:
            continue
        t = tier.get((r['ord'], r['gsis_id']))
        if t is not None:
            sv[_tier_label(r['position'], t)].append(sn)
        snap_per_player[(r['position'], r['gsis_id'])].append(sn)
    tier_snap_mean = {kk: float(statistics.mean(v)) for kk, v in sv.items()
                      if len(v) >= 50}
    k_snap = {}
    for pos in positions:
        vals = [v for (p_, _pid), v in snap_per_player.items()
                if p_ == pos and len(v) >= 4]
        if len(vals) < 30:
            continue
        within = statistics.mean(statistics.pvariance(v) for v in vals)
        between = statistics.pvariance([statistics.mean(v) for v in vals])
        if between > 0:
            k_snap[pos] = float(within / between)
    if not tier_snap_mean or not k_snap:
        # NAMED, NOT DEGRADED SILENTLY. Without these two `assign_tiers` has
        # no scale on which to place a no-history player against a veteran,
        # and it would fall back to the two-pass ordering this repair removed.
        return Outcome.blocked(
            'ROLE_PRIOR_SNAP_ANCHOR_UNIDENTIFIED',
            f'the snap-share tier anchor ({len(tier_snap_mean)} tier(s) at or '
            f'above 50 observations) or its shrinkage constant '
            f'({len(k_snap)} position(s)) is not identified from rows earlier '
            f'than {ordinal_cut}. The room ordering would have to be chosen '
            f'rather than estimated.', cause=Cause.DATA)

    # trailing snap share at the cut, for pricing prospective players
    latest = {pid: statistics.mean(h[-TRAIL:]) for pid, h in trail.items() if h}
    latest_n = {pid: len(h[-TRAIL:]) for pid, h in trail.items() if h}
    return Outcome.ok(
        'ROLE_PRIOR_OK',
        value={'tier_mean': tier_mean, 'k': k, 'trailing_snap': latest,
               'trailing_n': latest_n,
               'tier_snap_mean': tier_snap_mean, 'k_snap': k_snap,
               'n_history': {pid: len(v) for (_p, pid), v in
                             per_player.items()}},
        spec_version=SPEC_VERSION, cls_share=cls_share,
        ordinal_cut=ordinal_cut, n_rows=len(rows),
        tier_means={kk: round(vv, 5) for kk, vv in sorted(tier_mean.items())},
        shrinkage_k={kk: round(vv, 3) for kk, vv in sorted(k.items())},
        tier_snap_means={kk: round(vv, 5)
                         for kk, vv in sorted(tier_snap_mean.items())},
        shrinkage_k_snap={kk: round(vv, 3)
                          for kk, vv in sorted(k_snap.items())},
        note='k is within/between player variance of the class share; it is '
             'estimated, never chosen. k_snap and tier_snap_mean are the same '
             'construction in snap share, and are what orders a room.')


LEGACY_TWO_PASS = (
    'the prior carries no snap-share anchor (`tier_snap_mean`) or no '
    '`k_snap`, so the room cannot be placed on one scale and the pre-repair '
    'two-pass ordering is used. `build` always supplies both; a prior that '
    'does not is not one this repair can govern, and it says so here rather '
    'than pretending the repair applied.')


def _anchor(tsm, pos, t):
    """The measured mean snap share of tier `t` at position `pos`.

    Falls back to that position's own tiers, then to every tier, and never to
    a number written in this file.
    """
    v = tsm.get(_tier_label(pos, t))
    if v is not None:
        return v, 'tier'
    own = [vv for kk, vv in tsm.items() if kk.startswith(str(pos))]
    if own:
        return float(statistics.mean(own)), 'position_mean_of_tiers'
    return float(statistics.mean(tsm.values())), 'all_tiers_mean'


def assign_tiers(players, prior, depth_rank=None) -> dict:
    """Point-in-time tier for a prospective slate, on ONE scale.

    Every player in a (team, position) room is placed by the same expected
    snap share -- his own trailing value shrunk toward the anchor his CURRENT
    depth listing implies. There is no pass that ranks one group before
    another, which is what made a no-history chart-rank-1 player unpromotable.
    """
    trail = prior.get('trailing_snap') or {}
    tn = prior.get('trailing_n') or {}
    tsm = prior.get('tier_snap_mean') or {}
    ks = prior.get('k_snap') or {}
    depth_rank = depth_rank or {}
    grp = collections.defaultdict(list)
    for q in players:
        grp[(q.get('team'), q.get('position'))].append(q)
    out, basis, detail = {}, {}, {}

    if not tsm or not ks:
        # DECLARED DEGRADATION. Not a silent fallback: the caller is told,
        # by name, that the repaired ordering did not run.
        for _k, rs in grp.items():
            known = sorted([q for q in rs
                            if trail.get(q['gsis_id']) is not None],
                           key=lambda q: -trail[q['gsis_id']])
            for i, q in enumerate(known):
                out[q['gsis_id']] = i + 1
                basis[q['gsis_id']] = 'trailing_snap_share'
            rest = [q for q in rs if q['gsis_id'] not in out]
            ranked = sorted(
                [((depth_rank.get(q['gsis_id']) or 99), q['gsis_id'], q)
                 for q in rest])
            for j, (d, _pid, q) in enumerate(ranked):
                out[q['gsis_id']] = len(known) + j + 1
                basis[q['gsis_id']] = ('depth_chart' if d != 99
                                       else 'no_information_lowest_tier')
        return {'tier': out, 'basis': basis, 'detail': {},
                'spec_version': SPEC_VERSION, 'ordering': 'legacy_two_pass',
                'degraded': True, 'degraded_reason': LEGACY_TWO_PASS}

    k_default = float(statistics.mean(ks.values()))
    for (_team, pos), rs in grp.items():
        scored = []
        for q in rs:
            pid = q['gsis_id']
            own = trail.get(pid)
            n = int(tn.get(pid, 0) or 0) if own is not None else 0
            d = depth_rank.get(pid)
            has_d = d is not None
            # NO LISTING IS NOT TIER 1 AND IT IS NOT A GUESS: it anchors on
            # the deepest measured tier, which is what "the chart does not
            # carry him" has historically meant.
            anchor_tier = min(int(d), MAX_TIER) if has_d else MAX_TIER
            anchor, anchor_src = _anchor(tsm, pos, anchor_tier)
            kk = ks.get(pos, k_default)
            w = (n / (n + kk)) if n else 0.0
            score = (w * own + (1.0 - w) * anchor) if own is not None \
                else anchor
            if n and has_d:
                b = 'shrunk_trailing_and_depth'
            elif n:
                b = 'trailing_snap_share'
            elif has_d:
                b = 'depth_chart'
            else:
                b = 'no_information_lowest_tier'
            scored.append((-float(score), pid, q, {
                'score': float(score), 'own_trailing': own,
                'n_trailing': n, 'depth_rank': (int(d) if has_d else None),
                'anchor_tier': anchor_tier, 'anchor': float(anchor),
                'anchor_source': anchor_src, 'shrinkage_w': float(w),
                'k_snap': float(kk), 'basis': b}))
        scored.sort()
        for i, (_neg, pid, _q, det) in enumerate(scored):
            out[pid] = i + 1
            basis[pid] = det['basis']
            det['tier'] = i + 1
            det['room_size'] = len(scored)
            detail[pid] = det
    return {'tier': out, 'basis': basis, 'detail': detail,
            'spec_version': SPEC_VERSION,
            'ordering': 'single_scale_shrunk_expected_snap_share',
            'degraded': False}


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
