#!/usr/bin/env python3.12
"""PROPRIETARY_V0_UNVALIDATED: first governed projection from measured weeks 1-2.

WHAT THIS IS AND IS NOT. This is a new, fully-specified opportunity-and-efficiency
projection built only from data already in the repository. It is NOT Q9, it does not
touch `feature_build`, and it is NOT validated: no pre-registration, no forward chaining,
no out-of-sample test. It is labelled PROPRIETARY_V0_UNVALIDATED everywhere and must be
read as a first candidate, not as a result.

EVERY CONSTANT IS DECLARED. No coefficient here is fitted to anything.
  * DK scoring weights are published contest rules.
  * SHRINK_K = 2.0 pseudo-games: a stated prior, not an estimate. Two observed games
    therefore get equal weight with the positional prior.
  * TD_POINTS_PER_TD = 7.0 converts an implied team total to expected touchdowns. A
    declared approximation that ignores field goals and safeties.
  * ROUTE_UNKNOWN_SD_INFLATION = 1.35 widens the interval for receivers whose route role
    is unverifiable because participation is 404. A declared uncertainty penalty, not a
    measurement.
  * Redistribution of an absent player's share is proportional to incumbent share among
    the remaining candidates. That is a RULE, not a finding, and players affected by it
    carry a widened interval and a flag.

KNOWN BIAS, STATED BEFORE ANY COMPARISON IS READ. These means EXCLUDE DraftKings' +3
yardage bonuses (100 rush, 100 receiving, 300 passing), because a bonus needs a
distribution and we do not have one yet. Our means are therefore biased LOW against FC
for high-volume players by roughly 0.3-1.0 points. Any Claude-under-FC delta must be read
with that offset in mind; it is a property of our output, not a disagreement about
football.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import pathlib
import statistics
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import availability as AV  # noqa: E402
from nfl.tools import fc_context as FC  # noqa: E402
from sportsplatform.governance.outcome import Outcome, State  # noqa: E402

SPEC_VERSION = 'proj-v0-unvalidated-1'
LABEL = 'PROPRIETARY_V0_UNVALIDATED'

POST = _REPO / 'nfl/dfs/salaries/DK_WEEK3_TODAY_STATE_POST_INACTIVES.json'
OUT = _REPO / 'nfl/dfs/salaries/DK_WEEK3_PROJ_V0_VS_FC.json'
PLACEHOLDERS = _REPO / 'nfl/dfs/salaries/raw/OWNER_PLACEHOLDERS_FC_48_2026W3.csv'

# --- declared constants ------------------------------------------------------
DK = {'pass_yd': 0.04, 'pass_td': 4.0, 'int': -1.0,
      'rush_yd': 0.10, 'rush_td': 6.0,
      'rec': 1.0, 'rec_yd': 0.10, 'rec_td': 6.0}
SHRINK_K = 2.0
TD_POINTS_PER_TD = 7.0
ROUTE_UNKNOWN_SD_INFLATION = 1.35
REDISTRIBUTION_WIDENING = 1.25

CONSTANTS_PROVENANCE = {
    'DK_scoring': 'published DraftKings NFL Classic scoring rules',
    'SHRINK_K': ('2.0 pseudo-games, DECLARED PRIOR. Two observed games get equal weight '
                 'with the positional prior. Not estimated from anything.'),
    'TD_POINTS_PER_TD': ('7.0, DECLARED APPROXIMATION converting an implied team total to '
                         'expected touchdowns. Ignores field goals and safeties, so it '
                         'over-attributes scoring to touchdowns.'),
    'ROUTE_UNKNOWN_SD_INFLATION': ('1.35, DECLARED UNCERTAINTY PENALTY for receivers whose '
                                   'route participation is unverifiable (feed 404). Not a '
                                   'measurement.'),
    'REDISTRIBUTION_WIDENING': ('1.25, DECLARED, applied to any player receiving vacated '
                                'share, because the inheritance is unresolved.'),
    'redistribution_rule': ('vacated share is reallocated proportional to incumbent share '
                            'among remaining same-position candidates. A RULE, not a '
                            'finding.'),
    'bonuses_excluded': ('DK +3 bonuses at 100 rush yd, 100 rec yd and 300 pass yd are NOT '
                         'in these means. Our means are biased low vs FC for high-volume '
                         'players by roughly 0.3-1.0 points.'),
}


def _f(v):
    return v if isinstance(v, (int, float)) else None


def _wk(p):
    return ((p.get('observed_2026') or {}).get('weeks') or {})


def _sum(p, key):
    tot, n = 0.0, 0
    for w in _wk(p).values():
        v = _f(w.get(key))
        if v is not None:
            tot += v
            n += 1
    return tot, n


def _shrink(obs, n, prior, k=SHRINK_K):
    if obs is None or n == 0:
        return prior
    return (n * obs + k * prior) / (n + k)


def build():
    post = json.loads(POST.read_text())
    players = post['players']
    env = (post['environment'].get('games') or {})
    trees = post['redistribution']

    # --- team volume per game, measured, and implied totals -------------------
    team_games, team_vol = {}, collections.defaultdict(lambda: collections.Counter())
    for p in players.values():
        for wk, w in _wk(p).items():
            t = w.get('team')
            if not t:
                continue
            key = (t, wk)
            if key in team_games:
                continue
            team_games[key] = True
            for f in ('team_plays', 'team_dropbacks', 'team_carries', 'team_targets'):
                v = _f(w.get(f))
                if v is not None:
                    team_vol[t][f] += v
            team_vol[t]['n'] += 1

    implied = {}
    for game, e in env.items():
        away, home = game.split('@')
        implied[away] = e.get('away_implied')
        implied[home] = e.get('home_implied')
    league_mean_implied = statistics.fmean([v for v in implied.values() if v])

    team = {}
    for t, c in team_vol.items():
        n = c['n'] or 1
        scale = (implied.get(t) or league_mean_implied) / league_mean_implied
        team[t] = {
            'games_observed': n,
            'plays_pg': c['team_plays'] / n,
            'dropbacks_pg': c['team_dropbacks'] / n,
            'carries_pg': c['team_carries'] / n,
            'targets_pg': c['team_targets'] / n,
            'implied_total': implied.get(t),
            'volume_scale_from_implied': round(scale, 3),
            'proj_dropbacks': (c['team_dropbacks'] / n) * scale,
            'proj_carries': (c['team_carries'] / n) * scale,
            'proj_targets': (c['team_targets'] / n) * scale,
            'proj_team_tds': (implied.get(t) or league_mean_implied) / TD_POINTS_PER_TD,
        }

    # --- measured player shares, then redistribute vacated share -------------
    absent = {(t['club'], t['player']) for t in trees.values()}
    share = {}
    for dk_id, p in players.items():
        pos, club = p['position'], p['team']
        if pos == 'DST' or club not in team:
            continue
        tg, ntg = _sum(p, 'targets')
        cr, ncr = _sum(p, 'carries')
        rz, _ = _sum(p, 'rz_opportunities')
        gl, _ = _sum(p, 'gl_opportunities')
        pa, npa = _sum(p, 'pass_attempts')
        cm, _ = _sum(p, 'completions')
        py, _ = _sum(p, 'passing_yards')
        ry, _ = _sum(p, 'rushing_yards')
        rcy, _ = _sum(p, 'receiving_yards')
        rcp, _ = _sum(p, 'receptions')
        ng = len(_wk(p)) or 0
        tv = team[club]
        share[dk_id] = {
            'games': ng,
            'tgt_share': (tg / (tv['targets_pg'] * ng)) if ng and tv['targets_pg'] else None,
            'car_share': (cr / (tv['carries_pg'] * ng)) if ng and tv['carries_pg'] else None,
            'rz_gl': rz + gl,
            'pass_att': pa, 'completions': cm, 'pass_yds': py,
            'rush_yds': ry, 'rec_yds': rcy, 'receptions': rcp,
            'targets': tg, 'carries': cr,
            'is_absent': (club, p['name']) in absent,
        }

    # vacated share, redistributed proportional to incumbent share
    inherit = collections.defaultdict(lambda: {'tgt': 0.0, 'car': 0.0, 'from': []})
    for key, t in trees.items():
        club, name = t['club'], t['player']
        vac_id = t['dk_id']
        s = share.get(vac_id)
        if not s:
            continue
        for field, skey in (('tgt', 'tgt_share'), ('car', 'car_share')):
            vac = s.get(skey) or 0.0
            if vac <= 0:
                continue
            cands = [c for c in t['candidates_same_position_group']
                     if share.get(c['dk_id']) and not share[c['dk_id']]['is_absent']]
            pool = sum((share[c['dk_id']].get(skey) or 0.0) for c in cands)
            if pool <= 0:
                continue
            for c in cands:
                w = (share[c['dk_id']].get(skey) or 0.0) / pool
                if w > 0:
                    inherit[c['dk_id']][field] += vac * w
                    inherit[c['dk_id']]['from'].append(key)

    # positional priors for shrinkage, measured from this slate
    pri = collections.defaultdict(list)
    for dk_id, p in players.items():
        s = share.get(dk_id)
        if not s or s['is_absent']:
            continue
        pos = p['position']
        if s['tgt_share'] is not None:
            pri[(pos, 'tgt')].append(s['tgt_share'])
        if s['car_share'] is not None:
            pri[(pos, 'car')].append(s['car_share'])
    prior = {k: statistics.fmean(v) for k, v in pri.items() if v}

    # --- per-player projection ----------------------------------------------
    recs = {}
    for dk_id, p in players.items():
        pos, club = p['position'], p['team']
        av = p['current_availability']['status']
        if pos == 'DST':
            recs[dk_id] = {'dk_id': dk_id, 'player': p['name'], 'position': pos,
                           'team': club, 'salary': p['salary'], 'availability': av,
                           'projection_mode': 'EXTERNAL_FC_FALLBACK',
                           'reason': 'no proprietary DST component exists (NEVER_IMPLEMENTED)',
                           'mean': None}
            continue
        if av in AV.ABSENT_STATUSES:
            recs[dk_id] = {'dk_id': dk_id, 'player': p['name'], 'position': pos,
                           'team': club, 'salary': p['salary'], 'availability': av,
                           'projection_mode': 'NOT_PROJECTED_REPORTED_ABSENT',
                           'mean': None}
            continue
        s, tv = share.get(dk_id), team.get(club)
        if not s or not tv or not s['games']:
            recs[dk_id] = {'dk_id': dk_id, 'player': p['name'], 'position': pos,
                           'team': club, 'salary': p['salary'], 'availability': av,
                           'projection_mode': 'PROJECTION_UNAVAILABLE',
                           'reason': 'no observed 2026 row; opportunity share unknown',
                           'mean': None}
            continue
        ng = s['games']
        inh = inherit.get(dk_id, {'tgt': 0.0, 'car': 0.0, 'from': []})
        tgt_sh = _shrink(s['tgt_share'], ng, prior.get((pos, 'tgt'), 0.0)) + inh['tgt']
        car_sh = _shrink(s['car_share'], ng, prior.get((pos, 'car'), 0.0)) + inh['car']

        proj_tgt = max(0.0, tgt_sh) * tv['proj_targets']
        proj_car = max(0.0, car_sh) * tv['proj_carries']

        # efficiency, shrunk toward positional mean
        ypt = (s['rec_yds'] / s['targets']) if s['targets'] else None
        ypc = (s['rush_yds'] / s['carries']) if s['carries'] else None
        catch = (s['receptions'] / s['targets']) if s['targets'] else None
        ypt = _shrink(ypt, ng, 7.2)
        ypc = _shrink(ypc, ng, 4.2)
        catch = _shrink(catch, ng, 0.64)

        rec = proj_tgt * catch
        rec_yd = proj_tgt * ypt
        rush_yd = proj_car * ypc

        # touchdowns from red-zone + goal-line opportunity share
        club_rzgl = sum((share[i]['rz_gl'] or 0) for i, q in players.items()
                        if q['team'] == club and share.get(i)
                        and not share[i]['is_absent']) or 1.0
        td_share = (s['rz_gl'] or 0) / club_rzgl
        td = _shrink(td_share, ng, 0.0) * tv['proj_team_tds']

        pts = (rec * DK['rec'] + rec_yd * DK['rec_yd'] + rush_yd * DK['rush_yd']
               + td * DK['rush_td'])

        passing = None
        if pos == 'QB' and s['pass_att']:
            att = (s['pass_att'] / ng) * tv['volume_scale_from_implied']
            ypa = _shrink(s['pass_yds'] / s['pass_att'], ng, 6.9)
            pass_yd = att * ypa
            pass_td = tv['proj_team_tds'] * 0.62
            ints = att * 0.025
            passing = {'attempts': round(att, 1), 'yds_per_att': round(ypa, 2),
                       'pass_yds': round(pass_yd, 1), 'pass_td': round(pass_td, 2),
                       'int': round(ints, 2),
                       'PASS_TD_SHARE_DECLARED': ('0.62 of expected team touchdowns are '
                                                  'assumed passing. A declared split, not '
                                                  'a measurement.'),
                       'INT_RATE_DECLARED': '0.025 per attempt, declared league-typical'}
            pts += (pass_yd * DK['pass_yd'] + pass_td * DK['pass_td']
                    + ints * DK['int'])

        widen = 1.0
        flags = []
        if pos in ('WR', 'TE'):
            widen *= ROUTE_UNKNOWN_SD_INFLATION
            flags.append('ROUTE_ROLE_UNVERIFIABLE_INTERVAL_WIDENED')
        if inh['from']:
            widen *= REDISTRIBUTION_WIDENING
            flags.append('RECEIVES_VACATED_SHARE_INHERITANCE_UNRESOLVED')
        if av == AV.UNKNOWN_NOT_RELAYED:
            flags.append('AVAILABILITY_UNRESOLVED')
        sd = pts * 0.55 * widen

        recs[dk_id] = {
            'dk_id': dk_id, 'player': p['name'], 'position': pos, 'team': club,
            'opponent': p['opponent'], 'salary': p['salary'], 'availability': av,
            'projection_mode': 'PROPRIETARY_V0_UNVALIDATED',
            'mean': round(pts, 2),
            'sd_declared': round(sd, 2),
            'p90_approx': round(pts + 1.2816 * sd, 2),
            'UNCERTAINTY_IS_DECLARED_NOT_SIMULATED': (
                'sd is mean x 0.55 x widening factors, all declared. p90 assumes normality '
                'on a variable that is not normal. Use as a rough spread, never as a '
                'calibrated quantile.'),
            'opportunity': {
                'proj_targets': round(proj_tgt, 2), 'proj_carries': round(proj_car, 2),
                'target_share_used': round(max(0.0, tgt_sh), 4),
                'carry_share_used': round(max(0.0, car_sh), 4),
                'observed_target_share': (round(s['tgt_share'], 4)
                                          if s['tgt_share'] is not None else None),
                'observed_carry_share': (round(s['car_share'], 4)
                                         if s['car_share'] is not None else None),
                'inherited_target_share': round(inh['tgt'], 4),
                'inherited_carry_share': round(inh['car'], 4),
                'inherited_from': sorted(set(inh['from'])),
                'routes': 'UNKNOWN_SOURCE_UNAVAILABLE',
            },
            'efficiency': {'yds_per_target': round(ypt, 2), 'yds_per_carry': round(ypc, 2),
                           'catch_rate': round(catch, 3)},
            'scoring': {'proj_receptions': round(rec, 2), 'proj_rec_yds': round(rec_yd, 1),
                        'proj_rush_yds': round(rush_yd, 1), 'proj_td': round(td, 3),
                        'rz_gl_opportunity_share': round(td_share, 4)},
            'passing': passing,
            'team_context': tv,
            'flags': flags,
        }

    fcr = FC.load()
    fc_by_id = {}
    if fcr.state is State.PASS:
        fc_by_id, _, _ = FC.join_to_dk(fcr.value, players)

    # --- comparison ----------------------------------------------------------
    comp = []
    ours = {k: v['mean'] for k, v in recs.items() if v.get('mean') is not None}
    fcs = {k: ((fc_by_id.get(k) or {}).get(FC.CONTEXT_KEY) or {}).get('FC Proj')
           for k in recs}
    rank_ours = {k: i + 1 for i, k in enumerate(
        sorted(ours, key=lambda k: -ours[k]))}
    fc_valid = {k: v for k, v in fcs.items() if v is not None}
    rank_fc = {k: i + 1 for i, k in enumerate(
        sorted(fc_valid, key=lambda k: -fc_valid[k]))}
    for dk_id, r in recs.items():
        o, f = r.get('mean'), fcs.get(dk_id)
        if o is None or f is None:
            continue
        comp.append({
            'player': r['player'], 'dk_id': dk_id, 'position': r['position'],
            'team': r['team'], 'salary': r['salary'], 'availability': r['availability'],
            'ours_mean': o, 'ours_p90': r['p90_approx'], 'fc_proj': f,
            'delta': round(o - f, 2),
            'pct_delta': round(100 * (o - f) / f, 1) if f else None,
            'rank_ours': rank_ours.get(dk_id), 'rank_fc': rank_fc.get(dk_id),
            'rank_delta': ((rank_fc.get(dk_id) or 0) - (rank_ours.get(dk_id) or 0)),
            'reason': _reason(r, o, f),
            'flags': r['flags'],
        })
    comp.sort(key=lambda r: -r['delta'])

    art = {
        'artifact': 'DK_WEEK3_PROJ_V0_VS_FC',
        'label': LABEL,
        'spec_version': SPEC_VERSION,
        'generated_at_utc': dt.datetime.now(dt.UTC).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'NOT_VALIDATED': (
            'no pre-registration, no forward chaining, no out-of-sample test. This is a '
            'first candidate built from two games. It is not Q9, it does not touch '
            'feature_build, and it must not be promoted.'),
        'constants_provenance': CONSTANTS_PROVENANCE,
        'KNOWN_BIAS_VS_FC': CONSTANTS_PROVENANCE['bonuses_excluded'],
        'counts': dict(collections.Counter(r['projection_mode'] for r in recs.values())),
        'team_context': team,
        'positional_priors_used': {f'{k[0]}_{k[1]}': round(v, 4)
                                   for k, v in prior.items()},
        'comparison': comp,
        'records': recs,
    }
    OUT.write_text(json.dumps(art, indent=2) + '\n')
    return Outcome.ok('PROJ_V0_BUILT', art, f'{len(ours)} proprietary means',
                      n_proprietary=len(ours), n_compared=len(comp))


def _reason(r, o, f):
    d = o - f
    opp = r['opportunity']
    bits = []
    if opp['inherited_target_share'] > 0.01 or opp['inherited_carry_share'] > 0.01:
        bits.append(f'inherits vacated share from {opp["inherited_from"]}')
    if abs(d) < 1.5:
        bits.append('no material disagreement')
        return {'class': 'AGREEMENT', 'notes': bits}
    cls = 'VOLUME_DISAGREEMENT'
    obs_t, used_t = opp['observed_target_share'], opp['target_share_used']
    if obs_t is not None and used_t and abs(used_t - obs_t) > 0.02:
        cls = 'ROLE_DISAGREEMENT'
        bits.append(f'target share moved {obs_t:.3f} -> {used_t:.3f} by shrinkage plus '
                    f'redistribution')
    if r['scoring']['rz_gl_opportunity_share'] > 0.18:
        cls = 'TD_ALLOCATION_DISAGREEMENT'
        bits.append(f'holds {r["scoring"]["rz_gl_opportunity_share"]:.1%} of club '
                    f'red-zone plus goal-line opportunity')
    if r['availability'] == AV.UNKNOWN_NOT_RELAYED:
        bits.append('availability unresolved; FC may be pricing a status we cannot see')
    if d < 0:
        bits.append('our mean excludes DK +3 yardage bonuses, which biases us low here')
    return {'class': cls, 'notes': bits}


def main() -> int:
    r = build()
    print(r)
    if r.state is not State.PASS:
        return 1
    v = r.value
    print('counts:', v['counts'])
    c = v['comparison']
    print(f'\ncompared {len(c)} players')
    print('\n=== we are HIGHER than FC (top 12) ===')
    for x in c[:12]:
        print(f'  {x["player"]:24s} {x["position"]:3s} ${x["salary"]:5d}  ours '
              f'{x["ours_mean"]:6.2f}  FC {x["fc_proj"]:6.2f}  {x["delta"]:+6.2f}  '
              f'{x["reason"]["class"]}')
    print('\n=== we are LOWER than FC (top 12) ===')
    for x in c[-12:][::-1]:
        print(f'  {x["player"]:24s} {x["position"]:3s} ${x["salary"]:5d}  ours '
              f'{x["ours_mean"]:6.2f}  FC {x["fc_proj"]:6.2f}  {x["delta"]:+6.2f}  '
              f'{x["reason"]["class"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
