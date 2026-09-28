#!/usr/bin/env python3.12
"""Forward-chained evaluation on weeks the model has never seen, and arm selection on outcomes.

WHY THIS EXISTS AND WHAT IT REPLACES. V1's level sits about 17 per cent below an external board
on the top hundred players. The wrong way to close that is to tune toward the external board,
which the project's rules forbid and which would teach the model to agree with a competitor
rather than with football. The right way is to ask realised outcomes, on weeks that were not used
to build anything.

THE ONE CONSEQUENTIAL DECLARED CONSTANT. proj_v1.DEPTH_CLAIM_BLEND decides how much of a player's
allocated volume comes from his own multi-season claim against how much comes from the measured
depth curve for his rank. At 1.0 the claim decides everything, which over-allocates because claims
were earned alongside teammates now elsewhere. At 0.0 the depth curve decides everything, which
makes every club's first receiver identical and throws away who the player is. It was declared at
0.5 with no evidence. This module selects it on out-of-sample skill.

THE CHAIN. For each evaluation week W of a season S: the hierarchical prior sees seasons <= S-1
only; current-season evidence is restricted to weeks strictly before W; club volume likewise. The
projection is then scored against what actually happened in week W. Nothing from week W or later
enters any input. The prior for a season is identical across that season's weeks, so it is
computed once and reused, which is what makes this affordable.

TWO LIMITS, STATED UP FRONT BECAUSE THEY BOUND EVERY NUMBER BELOW.

  1 CONDITIONAL ON PLAYING. A player-week row exists in the panel only where a player appeared
    with an opportunity, and an absent row is UNKNOWN, never zero. So the evaluation set is
    players who PLAYED in week W. This measures allocation and efficiency skill GIVEN
    availability; it does not measure availability forecasting at all, and it flatters every arm
    equally by removing the hardest part of the problem. Correlations here are therefore upper
    bounds on live performance, and must not be quoted as live performance.
  2 WEEKS ARE NOT INDEPENDENT. Players within a week share game environments and clubs, so a
    naive standard error over player-weeks understates uncertainty. Differences between arms are
    reported with a week-blocked spread -- the arm comparison is paired by week, which is the
    right unit -- and a difference smaller than that spread is not a finding.

NO MARKET INPUT HERE. Historical closing lines are not held (OUT-036), so the club touchdown pool
comes from each club's own measured touchdown rate rather than from an implied total. That is a
declared difference from production, and it isolates the allocation question rather than mixing in
a market term the arms all share anyway.
"""
from __future__ import annotations

import collections
import json
import math
import pathlib
import statistics
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

SPEC_VERSION = 'forward-chain-1'
OUT = _REPO / 'nfl/derived/FORWARD_CHAIN.json'
OUT_CAP = _REPO / 'nfl/derived/FORWARD_CHAIN_PRIOR_CAP.json'

SKILL = ('QB', 'RB', 'WR', 'TE')

#: Arms. The blend values bracket the declared 0.5 at both ends, plus a V0-style arm that uses
#: current-season shares only and no multi-season prior at all -- the thing V1 replaced.
BLEND_ARMS = (0.0, 0.25, 0.5, 0.75, 1.0)
BASELINE_ARM = 'CURRENT_SEASON_ONLY'

#: Second sweep, run once the blend was selected. PRIOR_WEIGHT_CAP decides how much multi-season
#: evidence it takes to outweigh the current season: at 0 the prior is ignored entirely and the arm
#: should reproduce the baseline, at 24 a long career is nearly immovable. It was DECLARED at 12
#: with no evidence, and the first sweep's finding -- that the prior improves absolute error while
#: costing rank correlation -- points directly at it.
PRIOR_CAP_ARMS = (0.0, 2.0, 4.0, 8.0, 12.0, 24.0)


def arm_name(blend, cap):
    return f'blend{blend}_cap{cap}'

#: A week needs this many prior weeks of current-season evidence before it is evaluated, so the
#: current-season term is not built on one game.
MIN_PRIOR_WEEKS = 4

#: Inclusive week range to evaluate, as a one-element list so the CLI can set it. The default
#: starts after MIN_PRIOR_WEEKS. EVALUATING EARLY WEEKS SEPARATELY MATTERS: a constant selected on
#: weeks with four or more games of current-season evidence need not be right in week 3, when
#: there are two. The 2026 week-3 board dropped sharply under constants chosen on weeks 5+, which
#: is what prompted splitting the range.
WEEK_RANGE = [(MIN_PRIOR_WEEKS + 1, 99)]

DK = {'pass_yd': 0.04, 'pass_td': 4.0, 'int': -1.0, 'rush_yd': 0.1, 'rush_td': 6.0,
      'rec': 1.0, 'rec_yd': 0.1, 'rec_td': 6.0,
      'bonus_100_rush': 3.0, 'bonus_100_rec': 3.0, 'bonus_300_pass': 3.0}


def actual_dk(w):
    """Realised DK points for one player-week, from the panel. Bonuses are realised, not
    probabilistic, and fumbles are absent from the panel on both sides so they cancel."""
    py = w.get('pass_yards') or 0.0
    ry = w.get('rush_yards') or 0.0
    cy = w.get('rec_yards') or 0.0
    pts = (py * DK['pass_yd'] + (w.get('pass_td') or 0) * DK['pass_td']
           - (w.get('interceptions') or 0) * abs(DK['int'])
           + ry * DK['rush_yd'] + (w.get('rush_td') or 0) * DK['rush_td']
           + (w.get('receptions') or 0) * DK['rec'] + cy * DK['rec_yd']
           + (w.get('rec_td') or 0) * DK['rec_td'])
    if cy >= 100:
        pts += DK['bonus_100_rec']
    if ry >= 100:
        pts += DK['bonus_100_rush']
    if py >= 300:
        pts += DK['bonus_300_pass']
    return pts


def _spearman(xs, ys):
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    rx, ry = rank(xs), rank(ys)
    return _pearson(rx, ry)


def _pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sxy = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    sxx = sum((a - mx) ** 2 for a in xs)
    syy = sum((b - my) ** 2 for b in ys)
    return (sxy / math.sqrt(sxx * syy)) if sxx > 0 and syy > 0 else None


# ------------------------------------------------------- survivorship in the harness itself
def positions_for_chain(panel, pos_of):
    """Position for every player-season, inferring one where the roster cannot supply it.

    THE DEFECT THIS FIXES, WHICH WAS IN THE EVALUATION AND NOT THE MODEL. position_index() reads
    the roster blobs, and every blob in this repository is 2026 -- 60,331 rows, one season. So a
    player who left the league before 2026 has no position, and the chain's universe silently
    became 'players who survived to 2026'. Measured: 208 of 703 players classified in 2021, 356 of
    645 in 2023, 528 of 652 in 2025.

    That is not merely a smaller sample. Club totals are counted from the play rows and include
    everybody, so the volume of every unclassified player was redistributed among the survivors.
    It inflated the projected level by 67 per cent in 2021-2022 and by a smaller amount in the
    later seasons, and it selected for the better players, who are the ones still employed.

    Position is therefore inferred from usage where the roster is silent. QB and RB are reliable
    from usage. WR AND TE ARE NOT DISTINGUISHABLE from usage, so an inferred receiver is assigned
    WR and the assumption is recorded: it misplaces some tight ends into the receiver group split
    and depth curve. Inferred players are included in ALLOCATION, so the club total is shared with
    them as it should be, and EXCLUDED from the scored set, so a guessed position never enters a
    metric. Historical rosters are requested as OUT-038; this is a floor, not a fix.
    """
    out, inferred = {}, set()
    for gsis, seasons in panel['players'].items():
        known = pos_of.get(gsis)
        for season, weeks in seasons.items():
            if known:
                out[(gsis, int(season))] = known
                continue
            pa = sum((w.get('pass_attempts') or 0) for w in weeks.values())
            ca = sum((w.get('carries') or 0) for w in weeks.values())
            tg = sum((w.get('targets') or 0) for w in weeks.values())
            if pa >= 10 and pa >= ca and pa >= tg:
                pos = 'QB'
            elif ca > tg:
                pos = 'RB'
            elif tg > 0:
                pos = 'WR'
            else:
                continue
            out[(gsis, int(season))] = pos
            inferred.add((gsis, int(season)))
    return out, inferred


class _SeasonPos:
    """pos_of-compatible view for one season, so existing code needs no signature change."""

    def __init__(self, pos_map, season, fallback):
        self._m, self._s, self._f = pos_map, season, fallback

    def get(self, gsis, default=None):
        v = self._m.get((gsis, self._s))
        return v if v is not None else self._f.get(gsis, default)


# ------------------------------------------------------------------------------ the chain
def historical_band(panel, pos_of, gsis, pos, through):
    """The strongest band holding a quarter of a player's weighted evidence through `through`.

    Role state is not reconstructible for a historical week -- there are no predicted lineups
    and no injury reports in this repository for past Sundays -- so the evidence CEILING cannot
    be applied here. This is therefore a weaker band assignment than production uses, and it
    means the chain does NOT test the appearance adjustment or the starter cap. It tests the
    thing it is here to test: how volume is allocated once a band is known.
    """
    from nfl.tools import player_prior
    obs = player_prior._observations(panel, gsis, pos, through + 1, through)
    if not obs:
        return 'FRINGE'
    wt = collections.Counter()
    tot = 0.0
    for o in obs:
        w = player_prior._recency(o['seasons_back']) * min(1.0, o['touches'] / 8.0)
        wt[o['role_band']] += w
        tot += w
    if tot <= 0:
        return 'FRINGE'
    for band in reversed(player_prior.TIER_ORDER):
        if wt[band] / tot >= 0.25:
            return band
    return max(wt, key=lambda b: wt[b]) if wt else 'FRINGE'


def season_priors(panel, pos_of, season, gsis_list):
    """Priors for every player of interest, fitted on seasons <= season-1. Reused all season."""
    from nfl.tools import player_prior
    through = season - 1
    out = {}
    for gsis in gsis_list:
        pos = pos_of.get(gsis)
        if pos not in SKILL:
            continue
        band = historical_band(panel, pos_of, gsis, pos, through)
        out[gsis] = (band, player_prior.hierarchical(panel, gsis, pos, band, season, through))
    return out


def shares_before(panel, gsis, club, pos, season, week):
    """Measured current-season shares from weeks STRICTLY BEFORE `week`. No leakage."""
    cur = (panel['players'].get(gsis) or {}).get(str(season)) or {}
    tm = (panel['teams'].get(club) or {}).get(str(season)) or {}
    agg, tagg, n = collections.Counter(), collections.Counter(), 0
    for wk, w in cur.items():
        if int(wk) >= week:
            continue
        t = tm.get(wk)
        if not t:
            continue
        n += 1
        for f in ('targets', 'carries', 'pass_attempts', 'rz_targets', 'rz_carries',
                  'receptions', 'rec_yards', 'rush_yards', 'pass_yards', 'completions'):
            agg[f] += (w.get(f) or 0)
        for f in ('targets', 'rush_attempts', 'pass_attempts', 'rz_plays'):
            tagg[f] += (t.get(f) or 0)
    if not n:
        return {}, 0
    s = {}
    if tagg['targets']:
        s['target_share'] = agg['targets'] / tagg['targets']
        if tagg['rz_plays']:
            s['rz_target_share'] = agg['rz_targets'] / tagg['rz_plays']
    if tagg['rush_attempts']:
        s['carry_share'] = agg['carries'] / tagg['rush_attempts']
        if tagg['rz_plays']:
            s['rz_carry_share'] = agg['rz_carries'] / tagg['rz_plays']
    if tagg['pass_attempts']:
        s['pass_attempt_share'] = agg['pass_attempts'] / tagg['pass_attempts']
    if agg['targets'] >= 2:
        s['yards_per_target'] = agg['rec_yards'] / agg['targets']
        s['catch_rate'] = agg['receptions'] / agg['targets']
    if agg['carries'] >= 3:
        s['yards_per_carry'] = agg['rush_yards'] / agg['carries']
    if agg['pass_attempts'] >= 5:
        s['yards_per_attempt'] = agg['pass_yards'] / agg['pass_attempts']
        s['completion_rate'] = agg['completions'] / agg['pass_attempts']
    return s, n


def club_volume_before(panel, club, season, week, prior_games):
    """Club volume per game from weeks before `week`, blended with the prior season."""
    cur = (panel['teams'].get(club) or {}).get(str(season)) or {}
    prv = (panel['teams'].get(club) or {}).get(str(season - 1)) or {}
    FIELDS = ('plays', 'dropbacks', 'pass_attempts', 'rush_attempts', 'targets', 'rz_plays',
              'gl_plays', 'team_td')
    c_weeks = [w for k, w in cur.items() if int(k) < week]
    p_weeks = list(prv.values())
    if not c_weeks and not p_weeks:
        return None
    row = {}
    for f in FIELDS:
        pc = (sum((w.get(f) or 0) for w in c_weeks) / len(c_weeks)) if c_weeks else None
        pp = (sum((w.get(f) or 0) for w in p_weeks) / len(p_weeks)) if p_weeks else None
        if pc is None:
            v = pp
        elif pp is None:
            v = pc
        else:
            v = (len(c_weeks) * pc + prior_games * pp) / (len(c_weeks) + prior_games)
        row[f'proj_{f}'] = v
    row['state'] = 'OK'
    row['n_current_weeks'] = len(c_weeks)
    return row


def project_week(panel, pos_of, season, week, priors, depth, groups, bonus, ip, arm,
                 prior_games=4.0, prior_cap=None):
    """Project every player who appears in week `week`, using only earlier information."""
    from nfl.tools import proj_v1 as V
    from nfl.tools import td_rates as R

    # THE ALLOCATION POOL IS THE CLUB'S PLAUSIBLE ROSTER, NOT THE PLAYERS WHO TURNED OUT.
    #
    # This is the harness's second universe defect, and it is the one that made the chain
    # disagree with the live slate. Building the pool from players who appeared IN the scored week
    # gives about ten candidates per club, all of whom played. A DraftKings roster carries about
    # twenty-five, most of whom will not. A club's targets divided among ten certainties is a
    # different problem from the same targets divided among twenty-five candidates, and only the
    # second is the problem production solves. With the first universe the appearance term is
    # invisible -- every probability is 1 -- so the chain could neither see the defect it fixes nor
    # score the fix fairly.
    #
    # The pool is therefore every player with a row for that club in weeks STRICTLY BEFORE the
    # scored week, which is pregame information and leaks nothing. Membership is NOT taken from the
    # scored week: that would leak the fact that a player turned out. A debutant is consequently
    # absent from the pool and is not scored, which is a real and stated limit.
    pool_club = {}
    for gsis, seasons in panel['players'].items():
        if pos_of.get(gsis) not in SKILL:
            continue
        ss = seasons.get(str(season)) or {}
        last = None
        for wk in sorted((k for k in ss if int(k) < week), key=lambda k: int(k)):
            if ss[wk].get('team'):
                last = ss[wk]['team']
        if last:
            pool_club[gsis] = last
    universe = []
    for gsis, club in pool_club.items():
        pos = pos_of.get(gsis)
        w = ((panel['players'][gsis].get(str(season)) or {}).get(str(week))) or {}
        universe.append((gsis, pos, club, w))
    POOL[0] = set(pool_club)

    # PREDICTED-STARTER PROXY, and it fixes a specification error in this harness rather than
    # helping V1 along. Production applies the appearance adjustment to any quarterback who is not
    # his club's predicted starter; passing None here meant it never fired, so every backup
    # quarterback kept his full multi-season claim and SPLIT his club's attempts with the starter
    # -- precisely the Fields/Mahomes failure production now prevents. The baseline arm is immune,
    # because current-season usage already encodes who starts, so the comparison was
    # systematically unfair to V1 at quarterback, which is exactly where the per-position
    # breakdown showed V1 losing.
    #
    # The proxy is the club's rank-1 quarterback by pass attempts in weeks STRICTLY BEFORE the
    # scored week, falling back to the prior season. That is pregame information and introduces no
    # leakage. It is weaker than a real depth chart, so it understates the adjustment's value.
    qb_att = collections.defaultdict(dict)
    for gsis, seasons in panel['players'].items():
        if pos_of.get(gsis) != 'QB':
            continue
        cur = seasons.get(str(season)) or {}
        prv = seasons.get(str(season - 1)) or {}
        for wk, w in cur.items():
            if int(wk) < week and w.get('team'):
                qb_att[w['team']][gsis] = qb_att[w['team']].get(gsis, 0.0) + \
                    (w.get('pass_attempts') or 0)
        if not any(int(k) < week for k in cur):
            for wk, w in prv.items():
                if w.get('team'):
                    qb_att[w['team']][gsis] = qb_att[w['team']].get(gsis, 0.0) + \
                        0.25 * (w.get('pass_attempts') or 0)
    starter = {}
    for club, d in qb_att.items():
        if d:
            starter[club] = max(d, key=lambda g: d[g])

    _saved_cap = V.PRIOR_WEIGHT_CAP
    if prior_cap is not None:
        V.PRIOR_WEIGHT_CAP = prior_cap

    by_club = collections.defaultdict(list)
    rows = {}
    for gsis, pos, club, _w in universe:
        band, prior = priors.get(gsis, (None, None))
        cur, cur_n = shares_before(panel, gsis, club, pos, season, week)
        if arm == BASELINE_ARM:
            # V0-STYLE ARM: current season only, no multi-season prior at all. This is the thing
            # V1 replaced, and it is the arm that must be beaten for V1 to be worth anything.
            prior_used = {'measures': {}, 'tier': BASELINE_ARM, 'effective_obs_at_role': 0.0}
            band_used = band or 'FRINGE'
        else:
            prior_used = prior or {'measures': {}, 'tier': 'PRIOR_UNAVAILABLE',
                                   'effective_obs_at_role': 0.0}
            band_used = band or 'FRINGE'
        tv = club_volume_before(panel, club, season, week, prior_games)
        if not tv:
            continue
        is_start = (starter.get(club) == gsis) if pos == 'QB' else None
        r = V.project_player(panel, gsis, pos, band_used, club, tv, {}, cur, cur_n, prior_used,
                             is_predicted_starter=is_start, depth=depth)
        r.update({'gsis': gsis, 'team': club, 'position': pos, 'role_band': band_used,
                  'is_predicted_starter': is_start})
        rows[gsis] = r
        by_club[club].append(r)

    blend = None if arm == BASELINE_ARM else arm
    for club, crows in by_club.items():
        tv = club_volume_before(panel, club, season, week, prior_games)
        V.allocate_opportunity(crows, tv, depth, groups, blend=blend)
        for r in crows:
            V.finalize(r)
        # club touchdown pool from the club's OWN measured touchdown rate -- no market input
        pool = tv.get('proj_team_td')
        V_alloc = None
        if pool:
            V.allocate_club_td(pool, 0.6156, crows, PRATES[0])
    V.PRIOR_WEIGHT_CAP = _saved_cap
    out = {}
    for gsis, r in rows.items():
        pts, _items = V.dk_points(r, r.get('td'), bonus, ip)
        out[gsis] = pts
    return out


#: The role-transition set for the week being scored, as a one-element list so project_week and
#: the metric block can share it without threading another argument through.
TRANSITION = [set()]

#: The allocation pool for the week being scored, so the metric block can restrict the scored set
#: to pool members and never credit or blame a projection for a player who was not a candidate.
POOL = [set()]


#: Positional touchdown rates, loaded once. Held in a one-element list so project_week can see
#: them without threading another argument through every call site.
PRATES = [None]


def evaluate(panel, pos_of, seasons, arms, max_weeks=None):
    from nfl.tools import proj_v1 as V
    from nfl.tools import td_rates as R
    results = collections.defaultdict(list)
    per_week = []
    pos_map, inferred = positions_for_chain(panel, pos_of)
    for season in seasons:
        through = season - 1
        season_pos = _SeasonPos(pos_map, season, pos_of)
        excluded = {g for (g, s) in inferred if s == season}
        PRATES[0] = R.positional_rates(panel, pos_of)
        depth = V.depth_shares(panel, pos_of, through=through)
        groups = V.group_shares(panel, pos_of, through=through)
        bonus = V.bonus_rates(panel, pos_of, through=through)
        ip = V.int_rate(panel, pos_of)['int_per_attempt']
        weeks = sorted({int(w) for g, s in panel['players'].items()
                        for ss, ws in s.items() if int(ss) == season for w in ws})
        lo, hi = WEEK_RANGE[0]
        weeks = [w for w in weeks if lo <= w <= hi]
        if max_weeks:
            weeks = weeks[:max_weeks]
        gl = [g for g in panel['players'] if season_pos.get(g) in SKILL]
        priors = season_priors(panel, season_pos, season, gl)
        for week in weeks:
            # players whose current-season band disagrees with their multi-season band
            from nfl.tools import player_prior as _pp
            trans = set()
            for gsis, (band, _pr) in priors.items():
                pos = season_pos.get(gsis)
                if pos not in SKILL:
                    continue
                ss = (panel['players'].get(gsis) or {}).get(str(season)) or {}
                club = None
                for wk in sorted((k for k in ss if int(k) < week), key=int, reverse=True):
                    club = ss[wk].get('team')
                    if club:
                        break
                if not club:
                    continue
                cur, cur_n = shares_before(panel, gsis, club, pos, season, week)
                if cur_n < 2:
                    continue
                key = ('pass_attempt_share' if pos == 'QB'
                       else 'carry_share' if pos == 'RB' else 'target_share')
                cs = cur.get(key)
                if cs is None:
                    continue
                cur_band = _pp._band(pos, cs)
                if cur_band != band:
                    trans.add(gsis)
            TRANSITION[0] = trans
            # TWO SCORINGS, AND THE SECOND IS THE ONE THAT MATTERS FOR THE PRODUCT.
            #
            # CONDITIONAL: only players who appeared, each against his realised points. This
            # measures allocation and efficiency GIVEN availability and says nothing about
            # availability forecasting.
            #
            # UNCONDITIONAL (DFS): every pool candidate, and a candidate who did not appear scores
            # EXACTLY ZERO. For usage the panel's rule holds -- an absent row is UNKNOWN, never a
            # zero count. For DraftKings points it does not: a player you rostered who does not
            # play scores nothing, and that is a fact about the payoff rather than an inference
            # about his usage. This is the only scoring against which an UNCONDITIONAL projection
            # can be judged without bias. Scoring an appearance-discounted projection only on the
            # weeks a player turned out puts the level below 1.0 by construction, which is what
            # drove the ratio to 0.71 before this was separated.
            actual, actual_dfs = {}, {}
            for gsis, ss in panel['players'].items():
                if season_pos.get(gsis) not in SKILL or gsis in excluded:
                    continue
                w = (ss.get(str(season)) or {}).get(str(week))
                if w and w.get('team'):
                    actual[gsis] = actual_dk(w)
                    actual_dfs[gsis] = actual[gsis]
                elif gsis in POOL[0]:
                    actual_dfs[gsis] = 0.0
            if len(actual) < 50:
                continue
            wk_row = {'season': season, 'week': week, 'n_players': len(actual), 'arms': {}}
            for spec in arms:
                if isinstance(spec, tuple):
                    label, arm, cap = spec
                else:
                    label, arm, cap = str(spec), spec, None
                proj = project_week(panel, season_pos, season, week, priors, depth, groups,
                                    bonus, ip, arm, prior_cap=cap)
                common = [g for g in proj if g in actual and proj[g] is not None
                          and g in POOL[0]]
                if len(common) < 50:
                    continue
                dfs = [g for g in proj if g in actual_dfs and proj[g] is not None
                       and g in POOL[0]]
                xs = [proj[g] for g in common]
                ys = [actual[g] for g in common]
                n = len(common)
                mae = sum(abs(a - b) for a, b in zip(xs, ys)) / n
                rmse = math.sqrt(sum((a - b) ** 2 for a, b in zip(xs, ys)) / n)
                by_proj = sorted(common, key=lambda g: -proj[g])
                top30 = by_proj[:30]
                wk_row['arms'][label] = {
                    'n': n, 'mae': round(mae, 4), 'rmse': round(rmse, 4),
                    'pearson': (round(_pearson(xs, ys), 4) if _pearson(xs, ys) else None),
                    'spearman': (round(_spearman(xs, ys), 4) if _spearman(xs, ys) else None),
                    'mean_proj': round(statistics.fmean(xs), 4),
                    'mean_actual': round(statistics.fmean(ys), 4),
                    'level_ratio': round(statistics.fmean(xs) / statistics.fmean(ys), 4),
                    'top30_mean_actual': round(statistics.fmean([actual[g] for g in top30]), 4),
                }
                # the unconditional DFS scoring, over every candidate with a zero for absence
                if len(dfs) >= 50:
                    dx = [proj[g] for g in dfs]
                    dy = [actual_dfs[g] for g in dfs]
                    dn = len(dfs)
                    d_by = sorted(dfs, key=lambda g: -proj[g])
                    wk_row['arms'][label]['dfs'] = {
                        'n': dn,
                        'mae': round(sum(abs(a - b) for a, b in zip(dx, dy)) / dn, 4),
                        'rmse': round(math.sqrt(sum((a - b) ** 2 for a, b in zip(dx, dy)) / dn), 4),
                        'spearman': (round(_spearman(dx, dy), 4)
                                     if _spearman(dx, dy) is not None else None),
                        'pearson': (round(_pearson(dx, dy), 4)
                                    if _pearson(dx, dy) is not None else None),
                        'level_ratio': (round(statistics.fmean(dx) / statistics.fmean(dy), 4)
                                        if statistics.fmean(dy) else None),
                        'top30_mean_actual': round(
                            statistics.fmean([actual_dfs[g] for g in d_by[:30]]), 4),
                        'n_zero_actual': sum(1 for b in dy if b == 0.0)}
                # SLICE LEVEL, the apples-to-apples comparison with the external-board tripwire,
                # which fails on the top hundred and passes on the flat mean. A level that is
                # right overall can still be wrong exactly where lineups are built.
                for cut in (30, 50, 100):
                    sel = by_proj[:cut]
                    if len(sel) >= 20:
                        mp = statistics.fmean([proj[g] for g in sel])
                        ma = statistics.fmean([actual[g] for g in sel])
                        wk_row['arms'][label][f'level_ratio_top{cut}'] = round(mp / ma, 4)
                        wk_row['arms'][label][f'mean_proj_top{cut}'] = round(mp, 3)
                        wk_row['arms'][label][f'mean_actual_top{cut}'] = round(ma, 3)
                # ROLE-TRANSITION SUBSET. The aggregate says the multi-season prior does not
                # improve ranking. The hypothesis for why V1 exists anyway is that it earns its
                # place exactly where current-season usage and multi-season history DISAGREE --
                # a backup who inherited a workload, a star having a quiet fortnight, a starter
                # returning. That is a testable claim on this same data rather than a shield, so
                # it is tested: the subset is player-weeks whose band from weeks-before-W differs
                # from their band across earlier seasons. If the prior is worth its cost, it
                # should win HERE even while losing in aggregate. If it loses here too, the
                # hypothesis is wrong and should be withdrawn.
                trans = [g for g in common if g in TRANSITION[0]]
                if len(trans) >= 15:
                    tx = [proj[g] for g in trans]
                    ty = [actual[g] for g in trans]
                    wk_row['arms'][label]['transition'] = {
                        'n': len(trans),
                        'mae': round(sum(abs(a - b) for a, b in zip(tx, ty)) / len(trans), 4),
                        'spearman': (round(_spearman(tx, ty), 4)
                                     if _spearman(tx, ty) is not None else None),
                        'level_ratio': (round(statistics.fmean(tx) / statistics.fmean(ty), 4)
                                        if statistics.fmean(ty) else None)}
                # and the per-position breakdown, because a board can be right in aggregate and
                # wrong at one position
                bypos = collections.defaultdict(lambda: [[], []])
                for g in common:
                    bypos[season_pos.get(g)][0].append(proj[g])
                    bypos[season_pos.get(g)][1].append(actual[g])
                wk_row['arms'][label]['by_position'] = {
                    p: {'n': len(v[0]),
                        'level_ratio': round(statistics.fmean(v[0]) / statistics.fmean(v[1]), 4)
                        if statistics.fmean(v[1]) else None,
                        'mae': round(sum(abs(a - b) for a, b in zip(*v)) / len(v[0]), 3)}
                    for p, v in bypos.items() if len(v[0]) >= 10}
                results[label].append(wk_row['arms'][label])
            per_week.append(wk_row)
    return results, per_week


def summarise(results, per_week):
    """Per-arm skill, and the paired week-blocked comparison against the baseline arm.

    THE COMPARISON IS PAIRED BY WEEK. Players inside a week share game environments, clubs and
    weather, so a naive standard error over player-weeks understates uncertainty -- the same
    clustering error as naive binomial SEs on prop grading. Each arm is scored on the same weeks,
    the difference is taken within a week, and the spread of those differences across weeks is
    reported. A difference smaller than that spread is not a finding.
    """
    out = {}
    for arm, rows in results.items():
        if not rows:
            continue
        def m(k):
            v = [r[k] for r in rows if r.get(k) is not None]
            return round(statistics.fmean(v), 4) if v else None
        out[arm] = {'n_weeks': len(rows), 'mae': m('mae'), 'rmse': m('rmse'),
                    'pearson': m('pearson'), 'spearman': m('spearman'),
                    'level_ratio': m('level_ratio'),
                    'level_ratio_top30': m('level_ratio_top30'),
                    'level_ratio_top50': m('level_ratio_top50'),
                    'level_ratio_top100': m('level_ratio_top100'),
                    'top30_mean_actual': m('top30_mean_actual')}
    # unconditional DFS aggregates -- the decision-relevant scoring
    for arm in list(out):
        rows_d = [w['arms'][arm]['dfs'] for w in per_week
                  if arm in w['arms'] and w['arms'][arm].get('dfs')]
        if rows_d:
            out[arm]['dfs'] = {
                'n_weeks': len(rows_d),
                'mean_n_candidates': round(statistics.fmean(r['n'] for r in rows_d), 1),
                'mean_n_zero_actual': round(statistics.fmean(r['n_zero_actual']
                                                             for r in rows_d), 1),
                'mae': round(statistics.fmean(r['mae'] for r in rows_d), 4),
                'rmse': round(statistics.fmean(r['rmse'] for r in rows_d), 4),
                'spearman': round(statistics.fmean(r['spearman'] for r in rows_d
                                                   if r['spearman'] is not None), 4),
                'level_ratio': round(statistics.fmean(r['level_ratio'] for r in rows_d
                                                      if r['level_ratio'] is not None), 4),
                'top30_mean_actual': round(statistics.fmean(r['top30_mean_actual']
                                                            for r in rows_d), 4)}
    # transition-subset aggregates
    for arm in list(out):
        rows_t = [w['arms'][arm]['transition'] for w in per_week
                  if arm in w['arms'] and w['arms'][arm].get('transition')]
        if rows_t:
            out[arm]['transition'] = {
                'n_weeks': len(rows_t),
                'mean_n_players': round(statistics.fmean(r['n'] for r in rows_t), 1),
                'mae': round(statistics.fmean(r['mae'] for r in rows_t), 4),
                'spearman': round(statistics.fmean(r['spearman'] for r in rows_t
                                                   if r['spearman'] is not None), 4),
                'level_ratio': round(statistics.fmean(r['level_ratio'] for r in rows_t
                                                      if r['level_ratio'] is not None), 4)}
    base = out.get(BASELINE_ARM)
    if base:
        for arm, v in out.items():
            if arm == BASELINE_ARM:
                continue
            diffs = {}
            for k in ('mae', 'rmse', 'pearson', 'spearman', 'top30_mean_actual',
                      'transition.mae', 'transition.spearman',
                      'dfs.mae', 'dfs.spearman', 'dfs.top30_mean_actual'):
                d = []
                for w in per_week:
                    a, b = w['arms'].get(arm), w['arms'].get(BASELINE_ARM)
                    if not a or not b:
                        continue
                    if '.' in k:
                        grp, kk = k.split('.', 1)
                        a, b = a.get(grp), b.get(grp)
                        if not a or not b:
                            continue
                        k2 = kk
                    else:
                        k2 = k
                    if a.get(k2) is not None and b.get(k2) is not None:
                        d.append(a[k2] - b[k2])
                if len(d) >= 3:
                    mu = statistics.fmean(d)
                    sd = statistics.pstdev(d)
                    se = sd / math.sqrt(len(d))
                    diffs[k] = {'mean_difference': round(mu, 5),
                                'week_blocked_sd': round(sd, 5),
                                'week_blocked_se': round(se, 5),
                                'n_weeks_paired': len(d),
                                'exceeds_one_se': abs(mu) > se,
                                'exceeds_two_se': abs(mu) > 2 * se}
            v['vs_baseline_paired_by_week'] = diffs
    return out


def main() -> int:
    from nfl.tools import player_prior
    import sys as _s
    po = player_prior.load_panel()
    if po.state.name != 'PASS':
        print(po.render() if hasattr(po, 'render') else po)
        return 1
    panel = po.value
    pos_of = player_prior.position_index()
    seasons = [int(x) for x in (_s.argv[1].split(',') if len(_s.argv) > 1 else ['2024', '2025'])]
    mode = _s.argv[2] if len(_s.argv) > 2 else 'blend'
    if len(_s.argv) > 3 and '-' in _s.argv[3]:
        a, b = _s.argv[3].split('-')
        WEEK_RANGE[0] = (int(a), int(b))
    if mode == 'cap':
        arms = [(arm_name(1.0, c), 1.0, c) for c in PRIOR_CAP_ARMS] + [BASELINE_ARM]
    else:
        arms = [(str(b), b, None) for b in BLEND_ARMS] + [BASELINE_ARM]
    results, per_week = evaluate(panel, pos_of, seasons, arms)
    summary = summarise(results, per_week)
    labels = [(a[0] if isinstance(a, tuple) else str(a)) for a in arms]
    art = {'artifact': 'FORWARD_CHAIN', 'spec_version': SPEC_VERSION,
           'seasons': seasons, 'mode': mode, 'arms': labels,
           'week_range': list(WEEK_RANGE[0]),
           'baseline_arm': BASELINE_ARM, 'min_prior_weeks': MIN_PRIOR_WEEKS,
           'n_weeks_evaluated': len(per_week),
           'summary': summary, 'per_week': per_week,
           'CONDITIONAL_ON_PLAYING': (
               'the evaluation set is players who appeared in the scored week, because an absent '
               'panel row is UNKNOWN and never zero. These figures measure allocation and '
               'efficiency skill GIVEN availability. They do not measure availability '
               'forecasting, they flatter every arm equally, and they are upper bounds on live '
               'performance. Do not quote them as live performance.'),
           'NO_MARKET_INPUT': (
               'no historical closing lines are held (OUT-036), so the club touchdown pool comes '
               'from each club own measured touchdown rate rather than an implied total. A '
               'declared difference from production.'),
           'ROLE_STATE_NOT_RECONSTRUCTIBLE': (
               'predicted lineups and injury reports for past Sundays are not in this '
               'repository, so the evidence ceiling and the appearance adjustment are NOT '
               'exercised here. The chain tests allocation given a band, which is what it is '
               'for.')}
    (OUT_CAP if mode == 'cap' else OUT).write_text(
        json.dumps(art, indent=1, sort_keys=True, default=str))

    print(f'weeks evaluated: {len(per_week)}  seasons {seasons}')
    hdr = f"  {'arm':22s} {'wks':>3s} {'MAE':>7s} {'RMSE':>7s} {'r':>7s} {'rho':>7s} " \
          f"{'lvl':>6s} {'lvl30':>6s} {'lvl50':>6s} {'top30act':>8s}"
    print(hdr)
    for arm in labels:
        v = summary.get(arm)
        if not v:
            continue
        print(f"  {arm:22s} {v['n_weeks']:3d} {v['mae']:7.4f} {v['rmse']:7.4f} "
              f"{(v['pearson'] or 0):7.4f} {(v['spearman'] or 0):7.4f} "
              f"{(v['level_ratio'] or 0):6.3f} {(v['level_ratio_top30'] or 0):6.3f} "
              f"{(v['level_ratio_top50'] or 0):6.3f} {(v['top30_mean_actual'] or 0):8.3f}")
    print('\n  paired against the baseline arm, blocked by week:')
    for arm in labels:
        d = (summary.get(arm) or {}).get('vs_baseline_paired_by_week')
        if not d:
            continue
        for k in ('dfs.spearman', 'dfs.mae', 'dfs.top30_mean_actual',
                  'spearman', 'transition.spearman'):
            if k in d:
                x = d[k]
                flag = '**' if x['exceeds_two_se'] else ('*' if x['exceeds_one_se'] else '  ')
                print(f"    {arm:8s} {k:18s} {x['mean_difference']:+8.4f} "
                      f"+/- {x['week_blocked_se']:.4f} (week-blocked SE, n={x['n_weeks_paired']}) {flag}")
    print(f"  -> {(OUT_CAP if mode == 'cap' else OUT).relative_to(_REPO)}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
