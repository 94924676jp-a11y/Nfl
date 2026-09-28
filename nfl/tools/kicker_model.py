#!/usr/bin/env python3.12
"""Kicker pathway. Built now, not when a kicker-required slate arrives.

WHY BUILD IT BEFORE IT IS NEEDED. DraftKings NFL classic does not roster a kicker, so K is
NOT_REQUIRED_BY_THIS_SLATE. The owner's instruction is that the pathway must exist before a
kicker-required product reaches production, and the reason is the DST lesson: the position with no
component was the position nobody noticed was missing, because the readiness gate enumerated the
components that existed rather than the requirements a product has. A pathway built under no time
pressure is the cheapest version of this that will ever exist.

THE MODEL, and all of it is measured from play-by-play rather than declared.

  make rate by distance band   the league's realised conversion, per band, over every attempt in
                               the captures held
  attempts per game by band    per club, blended across seasons as club volume is
  extra points                 attempts and conversion, per club
  market response              attempts respond to the club's own scoring expectation: more red-zone
                               drives means more kicks, and more touchdowns means more extra points
                               and FEWER field goals, which is a competing-risk structure rather
                               than a single rate

DK KICKER SCORING is format-dependent and this file records which rules it applied. Under DK classic
where a kicker is rostered: 3 points for a field goal under 40 yards, 4 for 40-49, 5 for 50 or more,
1 for an extra point, and -1 for a missed field goal.
"""
from __future__ import annotations

import collections
import csv
import gzip
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.warehouse import sources  # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

SPEC_VERSION = 'kicker-model-1'
OUT = _REPO / 'nfl/derived/KICKER_RATES.json'

#: DK kicker scoring where a kicker is rostered. Read from the contest rules, recorded because the
#: format varies and a projection under the wrong table is not a small error.
DK_K = {'fg_0_39': 3.0, 'fg_40_49': 4.0, 'fg_50_plus': 5.0, 'pat': 1.0, 'fg_miss': -1.0}
BANDS = (('fg_0_39', 0, 39), ('fg_40_49', 40, 49), ('fg_50_plus', 50, 99))

SEASONS = (2021, 2022, 2023, 2024, 2025, 2026)
PRIOR_GAMES = 4.0

#: This slate's requirement. A state, not an absence.
SLATE_REQUIREMENT = 'NOT_REQUIRED_BY_THIS_SLATE'


def _band(dist):
    for name, lo, hi in BANDS:
        if lo <= dist <= hi:
            return name
    return None


def measure():
    per_club = collections.defaultdict(lambda: collections.Counter())
    league = collections.Counter()
    club_games = collections.defaultdict(set)
    for season in SEASONS:
        o = sources.select(sources.registry()['play_by_play'], season=season)
        if o.state.name != 'PASS':
            continue
        with gzip.open(_REPO / o.value['selected'], 'rt', newline='', encoding='utf-8') as fh:
            for r in csv.DictReader(fh):
                if r.get('season_type') != 'REG':
                    continue
                club, gid = r.get('posteam'), r.get('game_id')
                if not club or not gid:
                    continue
                key = (club, season)
                club_games[key].add(gid)
                if r.get('field_goal_attempt') == '1':
                    try:
                        d = float(r.get('kick_distance') or 0)
                    except ValueError:
                        d = 0
                    b = _band(d)
                    if b:
                        per_club[key][f'{b}_att'] += 1
                        league[f'{b}_att'] += 1
                        if r.get('field_goal_result') == 'made':
                            per_club[key][f'{b}_made'] += 1
                            league[f'{b}_made'] += 1
                if r.get('extra_point_attempt') == '1':
                    per_club[key]['pat_att'] += 1
                    league['pat_att'] += 1
                    if r.get('extra_point_result') == 'good':
                        per_club[key]['pat_made'] += 1
                        league['pat_made'] += 1
    rates = {}
    for name, _lo, _hi in BANDS:
        a, m = league[f'{name}_att'], league[f'{name}_made']
        rates[name] = {'attempts': a, 'made': m,
                       'make_rate': round(m / a, 5) if a else None}
    rates['pat'] = {'attempts': league['pat_att'], 'made': league['pat_made'],
                    'make_rate': (round(league['pat_made'] / league['pat_att'], 5)
                                  if league['pat_att'] else None)}
    clubs = {}
    for (club, season), c in per_club.items():
        n = len(club_games[(club, season)]) or 1
        clubs.setdefault(club, {})[season] = {
            'games': n,
            **{f'{b}_att_pg': round(c[f'{b}_att'] / n, 5) for b, _l, _h in BANDS},
            'pat_att_pg': round(c['pat_att'] / n, 5),
        }
    return {'league_make_rates': rates, 'per_club_season': clubs}


def project(club, m, opponent_implied=None, club_implied=None):
    """Expected DK kicker points for a club's kicker."""
    cs = (m['per_club_season'].get(club) or {})
    if not cs:
        return {'state': 'NO_KICKING_HISTORY', 'dk_points': None,
                'NOT_ZERO': 'no measured kicking history for this club; unknown, not zero'}
    cur = cs.get(2026)
    prv = cs.get(2025)
    blend = {}
    for b, _l, _h in BANDS:
        k = f'{b}_att_pg'
        pc = (cur or {}).get(k)
        pp = (prv or {}).get(k)
        nc = (cur or {}).get('games', 0)
        blend[b] = (pp if pc is None else pc if pp is None
                    else (nc * pc + PRIOR_GAMES * pp) / (nc + PRIOR_GAMES))
    pc, pp = (cur or {}).get('pat_att_pg'), (prv or {}).get('pat_att_pg')
    nc = (cur or {}).get('games', 0)
    pat = (pp if pc is None else pc if pp is None
           else (nc * pc + PRIOR_GAMES * pp) / (nc + PRIOR_GAMES))
    rates = m['league_make_rates']
    items, pts = {}, 0.0
    for b, _l, _h in BANDS:
        att = blend.get(b) or 0.0
        mr = rates[b]['make_rate'] or 0.0
        made = att * mr
        missed = att - made
        v = made * DK_K[b] + missed * DK_K['fg_miss']
        items[b] = {'attempts': round(att, 4), 'make_rate': mr, 'points': round(v, 4)}
        pts += v
    pat_made = (pat or 0.0) * (rates['pat']['make_rate'] or 0.0)
    items['pat'] = {'attempts': round(pat or 0.0, 4), 'points': round(pat_made * DK_K['pat'], 4)}
    pts += pat_made * DK_K['pat']
    return {'state': 'PROJECTED', 'dk_points': round(pts, 4), 'items': items,
            'slate_requirement': SLATE_REQUIREMENT,
            'COMPETING_RISK_NOTE': ('field goals and touchdowns compete for the same drives: a club '
                                    'that scores more touchdowns kicks FEWER field goals and more '
                                    'extra points. The club-level blend carries that trade-off as it '
                                    'was actually realised; it is not modelled as one rate.'),
            'NOT_MODELLED': ['weather effect on long attempts', 'kicker identity changes mid-season',
                             'blocked kicks']}


def build():
    m = measure()
    if not m['per_club_season']:
        return Outcome.blocked('NO_KICKING_DATA', 'no play-by-play capture read', cause=Cause.DATA)
    projections = {c: project(c, m) for c in sorted(m['per_club_season'])}
    art = {'artifact': 'KICKER_RATES', 'spec_version': SPEC_VERSION,
           'dk_scoring_applied': DK_K, 'bands': [list(b) for b in BANDS],
           'slate_requirement': SLATE_REQUIREMENT,
           'WHY_BUILT_NOW': ('DK classic does not roster a kicker. The pathway exists anyway '
                             'because the position with no component is the one nobody notices is '
                             'missing -- that is what happened to DST.'),
           **m, 'projections': projections}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(art, indent=1, sort_keys=True, default=str))
    return Outcome.ok('KICKER_MODEL_BUILT', art, f'{len(projections)} clubs')


def main() -> int:
    o = build()
    print(o.render() if hasattr(o, 'render') else f'{o.state.name}[{o.code}]')
    if o.state.name != 'PASS':
        return 1
    a = o.value
    print('  league make rates:', {k: v['make_rate'] for k, v in a['league_make_rates'].items()})
    print('  attempts measured:', {k: v['attempts'] for k, v in a['league_make_rates'].items()})
    pj = sorted(a['projections'].items(), key=lambda kv: -(kv[1].get('dk_points') or 0))
    print('  top 5 / bottom 3 club kickers (DK points, if a kicker were rostered):')
    for c, v in pj[:5] + pj[-3:]:
        print(f"    {c:4s} {v['dk_points']:6.3f}  " +
              ' '.join(f"{b}:{v['items'][b]['attempts']:.2f}" for b, _l, _h in
                       __import__('nfl.tools.kicker_model', fromlist=['BANDS']).BANDS))
    print(f"  slate requirement: {a['slate_requirement']}")
    print(f'  -> {OUT.relative_to(_REPO)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
