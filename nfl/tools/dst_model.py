#!/usr/bin/env python3.12
"""Defence and special teams. The one rosterable position with no component at all.

WHY IT WAS MISSING, which matters more than the fact that it was. The Week 3 postmortem found
that pregame_readiness.py contains zero occurrences of the strings 'DST' and 'position', so the
readiness gate enumerated the components that existed rather than the requirements a product
has. A position with no player-level features has nothing whose absence anybody notices, so it
was structurally unrepresentable in the gate and stayed missing for the entire build. DST is
therefore not an oversight to patch; it is what the gate could not see.

WHAT A DST PROJECTION IS UNDER DK CLASSIC SCORING. Two independent pieces:

  1 EVENT PRODUCTION -- sacks, interceptions, fumble recoveries, return touchdowns, safeties and
    blocked kicks. Measured per club from play-by-play and blended across seasons, exactly as
    club offensive volume is.
  2 POINTS ALLOWED -- a step function, and the single largest term. Ten points for a shutout
    down to minus four for allowing 35. It is not a mean: a defence facing an opponent implied
    for 20 does NOT score the bucket that 20 falls in, it scores the expectation over the whole
    distribution of what that opponent might score. So the market's number is the centre and the
    spread has to be integrated over.

THE SPREAD IS NON-PARAMETRIC AND HONESTLY TOO WIDE. Residuals of actual club points around the
league mean are measured and reused as the conditional spread around each opponent's implied
total. That overstates the conditional spread, because some of the variation between clubs is
predictable and the market already prices it. An overwide spread pulls the points-allowed
expectation toward the middle buckets, so this term is CONSERVATIVE rather than sharp -- it will
understate a great defence against a weak offence and overstate the reverse. Fixing it needs
historical closing lines to residualise against, which this repository does not hold; requested
as OUT-036. The bias direction is recorded rather than the number being invented.

NOT MODELLED, and recorded rather than omitted silently: opponent-specific matchup (a club's
sack rate is its own, not adjusted for the line it faces), and the two-point-return score.
"""
from __future__ import annotations

import collections
import csv
import gzip
import json
import pathlib
import statistics
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

SPEC_VERSION = 'dst-model-1'
PBP_DIR = _REPO / 'nfl/research/postgame'
OUT = _REPO / 'nfl/derived/DST_RATES.json'

#: Seasons used to estimate club defensive rates. Includes 2026 for the CURRENT club's form,
#: which is legitimate here because these are the club's own realised events, not a fitted
#: coefficient -- but the residual spread is estimated on <= 2025 only.
RATE_SEASONS = (2021, 2022, 2023, 2024, 2025, 2026)
RESIDUAL_THROUGH = 2025

#: Pseudo-games of prior-season defensive form mixed into the current season. DECLARED, and the
#: same figure used for club offensive volume, for the same reason: two games is a thin estimate
#: of a unit and a defence does not reset in September.
PRIOR_GAMES = 4.0

#: DK Classic DST scoring, read from the contest rules.
DK_DST = {'sack': 1.0, 'interception': 2.0, 'fumble_recovery': 2.0, 'return_td': 6.0,
          'safety': 2.0, 'blocked_kick': 2.0}

#: Points-allowed buckets: (inclusive_low, inclusive_high_or_None, points).
PA_BUCKETS = ((0, 0, 10.0), (1, 6, 7.0), (7, 13, 4.0), (14, 20, 1.0),
              (21, 27, 0.0), (28, 34, -1.0), (35, None, -4.0))

CONSTANTS_PROVENANCE = {
    'DK_DST': (DK_DST, 'DraftKings Classic DST scoring, read from contest rules.'),
    'PA_BUCKETS': (PA_BUCKETS, 'DraftKings points-allowed step function, read from rules.'),
    'PRIOR_GAMES': (PRIOR_GAMES, 'DECLARED pseudo-games of prior-season defensive form.'),
    'RESIDUAL_THROUGH': (RESIDUAL_THROUGH,
                         'residual spread fitted at or before this season so the current one '
                         'is not used to build its own spread.'),
}


def _capture(season):
    hits = sorted(PBP_DIR.glob(f'pbp_{season}.*.csv.gz'))
    return max(hits, key=lambda p: p.stat().st_size) if hits else None


def measure():
    """Per club-week defensive events and points allowed, from play-by-play."""
    per = collections.defaultdict(lambda: collections.Counter())
    games = {}
    for season in RATE_SEASONS:
        path = _capture(season)
        if not path:
            continue
        with gzip.open(path, 'rt', newline='') as fh:
            for r in csv.DictReader(fh):
                if r.get('season_type') != 'REG':
                    continue
                gid, wk = r.get('game_id'), r.get('week')
                dt, pt = r.get('defteam'), r.get('posteam')
                if not gid:
                    continue
                g = games.setdefault(gid, {'season': season, 'week': wk,
                                           'home': r.get('home_team'), 'away': r.get('away_team'),
                                           'hs': 0.0, 'as': 0.0})
                for k, fld in (('hs', 'home_score'), ('as', 'away_score')):
                    try:
                        g[k] = float(r[fld])
                    except (TypeError, ValueError, KeyError):
                        pass
                # RETURN SCORES ARE CREDITED FROM td_team, NOT FROM defteam. On a kickoff
                # nflfastR makes posteam the RECEIVING team, so defteam is the kicking team and
                # crediting defteam gave every kickoff return score to the wrong defence. That
                # put New England's return touchdowns at 0.32 a game against a league norm near
                # 0.1. Reading the club that actually scored is convention-independent.
                if r.get('return_touchdown') == '1':
                    tdt = r.get('td_team')
                    if tdt and tdt != pt:
                        per[(tdt, season, wk)]['return_td'] += 1
                # A TAKEAWAY IS CREDITED TO WHOEVER RECOVERED, when that differs from whoever
                # fumbled. Keying on defteam missed a muffed punt recovered by the kicking team,
                # which is that unit's takeaway.
                if r.get('fumble') == '1':
                    rec, lost = r.get('fumble_recovery_1_team'), r.get('fumbled_1_team')
                    if rec and lost and rec != lost:
                        per[(rec, season, wk)]['fumble_recovery'] += 1
                if not dt:
                    continue
                key = (dt, season, wk)
                c = per[key]
                if r.get('sack') == '1':
                    c['sack'] += 1
                if r.get('interception') == '1':
                    c['interception'] += 1
                if r.get('safety') == '1':
                    c['safety'] += 1
                if r.get('punt_blocked') == '1':
                    c['blocked_kick'] += 1
                c['plays_faced'] += 1
    # points allowed per club-week
    for gid, g in games.items():
        if not g['home'] or not g['away']:
            continue
        for club, allowed in ((g['home'], g['as']), (g['away'], g['hs'])):
            k = (club, g['season'], g['week'])
            if k in per:
                per[k]['points_allowed'] = allowed
                per[k]['has_pa'] = 1
    return per, games


def residual_spread(per):
    """Non-parametric residuals of club points around the league mean, fitted <= 2025."""
    pts = [c['points_allowed'] for (club, s, w), c in per.items()
           if c.get('has_pa') and s <= RESIDUAL_THROUGH]
    if len(pts) < 200:
        return {'state': 'NOT_ESTIMATED', 'n': len(pts)}
    mean = statistics.fmean(pts)
    res = sorted(p - mean for p in pts)
    return {'state': 'MEASURED', 'n_club_games': len(res),
            'league_mean_points': round(mean, 4),
            'sd': round(statistics.pstdev(pts), 4),
            'residuals': [round(x, 3) for x in res],
            'SPREAD_IS_UNCONDITIONAL_AND_THEREFORE_TOO_WIDE': (
                'these residuals are around the LEAGUE mean, not around each club-game own '
                'market expectation, because no line history is held. Part of this spread is '
                'predictable and already priced. Using it as the conditional spread pulls the '
                'points-allowed expectation toward the middle buckets, so the term is '
                'conservative: it understates a strong defence facing a weak offence and '
                'overstates the reverse. OUT-036 would fix it.')}


def pa_expectation(implied_allowed, spread):
    """Expected DK points-allowed score, integrating over the residual distribution."""
    if implied_allowed is None or spread.get('state') != 'MEASURED':
        return None, {'state': 'NOT_COMPUTABLE',
                      'reason': 'no opponent implied total' if implied_allowed is None
                                else 'no residual spread'}
    res = spread['residuals']
    n = len(res)
    tally = collections.Counter()
    ev = 0.0
    for r in res:
        pts = implied_allowed + r
        for lo, hi, val in PA_BUCKETS:
            if pts >= lo - 0.5 and (hi is None or pts <= hi + 0.5):
                ev += val
                tally[f'{lo}-{hi if hi is not None else "plus"}'] += 1
                break
    return ev / n, {'state': 'COMPUTED', 'centre_implied_allowed': implied_allowed,
                    'bucket_probabilities': {k: round(v / n, 5)
                                             for k, v in sorted(tally.items())},
                    'n_residuals': n,
                    'NOT_THE_BUCKET_THE_MEAN_FALLS_IN': (
                        'a defence facing an opponent implied for 20 does not score the 14-20 '
                        'bucket; it scores the expectation over everything that opponent might '
                        'score. Reading the mean bucket alone would be a different and wrong '
                        'quantity.')}


#: A measured zero is rejected as a capture defect when it is this improbable under the league
#: rate. DECLARED threshold. The live case: the 2025 capture credits the New York Jets defence
#: with ZERO interceptions across 1,419 defensive plays while 31 of 32 clubs recorded some and
#: the next-lowest recorded six. All 13 interceptions in Jets games were thrown BY the Jets, so
#: opposing quarterbacks threw none against them all season. Against the measured league rate of
#: 0.7534 per game the expectation over 19 club-weeks is 14.3, and P(0) is about 6e-7. That is a
#: defect in the capture, not a property of the defence, and reporting it as a zero would have
#: silently removed an entire scoring term from that club's projection.
IMPLAUSIBLE_ZERO_P = 1e-4


def _poisson_zero_p(lam):
    """P(X = 0) for X ~ Poisson(lam). Uses exp directly; lam here is never large enough to
    overflow, and a tiny result is exactly the signal we want."""
    import math
    return math.exp(-lam) if lam < 700 else 0.0


def league_rates(per):
    """League per-club-game event rates, the reference for the plausibility test."""
    tot, n = collections.Counter(), 0
    for (club, s, w), c in per.items():
        if not c.get('has_pa'):
            continue
        n += 1
        for k in DK_DST:
            tot[k] += c[k]
    return ({k: (v / n if n else None) for k, v in tot.items()}, n)


def club_rates(per):
    """Per-club event rates per game, current season blended with prior season."""
    cur, prv = collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter)
    ngames = {'cur': collections.Counter(), 'prv': collections.Counter()}
    for (club, season, wk), c in per.items():
        if season == 2026:
            for k in DK_DST:
                cur[club][k] += c[k]
            ngames['cur'][club] += 1
        elif season == 2025:
            for k in DK_DST:
                prv[club][k] += c[k]
            ngames['prv'][club] += 1
    lg, _lgn = league_rates(per)
    out = {}
    for club in set(list(cur) + list(prv)):
        nc, np_ = ngames['cur'][club], ngames['prv'][club]
        row = {'games_2026': nc, 'games_2025': np_, 'implausible_zeros': {}}
        for k in DK_DST:
            pc = (cur[club][k] / nc) if nc else None
            pp = (prv[club][k] / np_) if np_ else None
            if pc is None and pp is None:
                row[k] = None
            elif pc is None:
                row[k] = pp
            elif pp is None:
                row[k] = pc
            else:
                row[k] = (nc * pc + PRIOR_GAMES * pp) / (nc + PRIOR_GAMES)
            row[f'{k}_2026_pg'] = round(pc, 4) if pc is not None else None
            row[f'{k}_2025_pg'] = round(pp, 4) if pp is not None else None
            # A ZERO THIS IMPROBABLE IS A CAPTURE DEFECT, NOT A DEFENCE. The league rate is
            # substituted -- itself a measurement, not an invented constant -- and the row is
            # labelled so the substitution travels with the number instead of vanishing into it.
            games = nc + np_
            total_events = cur[club][k] + prv[club][k]
            if total_events == 0 and games >= 8 and lg.get(k):
                lam = lg[k] * games
                pz = _poisson_zero_p(lam)
                if pz < IMPLAUSIBLE_ZERO_P:
                    row['implausible_zeros'][k] = {
                        'observed_events': 0, 'club_games': games,
                        'league_rate_per_game': round(lg[k], 5),
                        'expected_under_league_rate': round(lam, 3),
                        'p_of_observing_zero': f'{pz:.3g}',
                        'action': 'LEAGUE_RATE_SUBSTITUTED',
                        'WHY': 'a zero this improbable is a defect in the capture, not a '
                               'property of the defence. Reporting it would have deleted a '
                               'whole scoring term from this club silently.'}
                    row[k] = lg[k]
        out[club] = row
    return out


def project(club, opponent_implied, rates, spread):
    """One DST projection: measured event production plus the points-allowed expectation."""
    r = rates.get(club)
    if not r:
        return {'state': 'NO_DEFENSIVE_HISTORY', 'dk_points': None,
                'NOT_ZERO': 'no measured defensive history for this club; unknown, not zero'}
    items, missing = {}, []
    substituted = r.get('implausible_zeros') or {}
    for k, w in DK_DST.items():
        v = r.get(k)
        if v is None:
            missing.append(k)
            continue
        items[k] = round(v * w, 4)
    pa, pa_acct = pa_expectation(opponent_implied, spread)
    if pa is None:
        return {'state': 'POINTS_ALLOWED_NOT_COMPUTABLE', 'dk_points': None,
                'event_items': items, 'points_allowed_account': pa_acct,
                'NOT_ZERO': 'the largest scoring term could not be computed, so no total is '
                            'emitted. A partial total would read as a full one.'}
    items['points_allowed'] = round(pa, 4)
    return {'state': ('PROJECTED' if not substituted
                      else 'PROJECTED_WITH_LEAGUE_RATE_SUBSTITUTION'),
            'dk_points': round(sum(items.values()), 4),
            'event_items': items, 'points_allowed_account': pa_acct,
            'measures_missing': missing,
            'implausible_zeros_substituted': substituted,
            'games_2026': r.get('games_2026'), 'games_2025': r.get('games_2025'),
            'NOT_MODELLED': ['opponent-specific matchup adjustment',
                             'two-point conversion return']}


def build():
    if not _capture(2025):
        return Outcome.blocked('DST_NO_PBP', 'no play-by-play capture found', cause=Cause.DATA)
    per, games = measure()
    spread = residual_spread(per)
    rates = club_rates(per)
    art = {'artifact': 'DST_RATES', 'spec_version': SPEC_VERSION,
           'n_club_weeks_measured': len(per), 'n_games': len(games),
           'residual_spread': {k: v for k, v in spread.items() if k != 'residuals'},
           'n_residuals': len(spread.get('residuals') or ()),
           'club_rates': rates,
           'league_rates_per_club_game': {k: (round(v, 5) if v is not None else None)
                                          for k, v in league_rates(per)[0].items()},
           'implausible_zeros_found': {c: list(r['implausible_zeros'])
                                       for c, r in rates.items() if r.get('implausible_zeros')},
           'IMPLAUSIBLE_ZERO_P': IMPLAUSIBLE_ZERO_P,
           'CONSTANTS_PROVENANCE': {k: [v[0], v[1]] for k, v in CONSTANTS_PROVENANCE.items()},
           'WHY_THIS_WAS_MISSING': (
               'pregame_readiness.py contains zero occurrences of DST or position, so the gate '
               'enumerated existing components instead of product requirements. A position with '
               'no player-level features has nothing whose absence is noticed.')}
    OUT.write_text(json.dumps(art, indent=1, sort_keys=True, default=str))
    return art, spread, rates
