"""D4 and D5 production priors, read from the frozen research fits.

WHAT WAS WRONG BEFORE THIS

`receiving_conversion` took `catch_rate` and `yards_per_reception` from its
caller and computed Y = R x ypr. Two defects in one line:

1. The numbers were the caller's, not RC1's. A layer that accepts any prior is
   not an implementation of a particular baseline.
2. A CONSTANT yards-per-reception collapses the per-catch spread. RC1's own
   addendum measures why that is not a rounding matter: per-reception yardage
   has skew 2.197 and excess kurtosis 7.830, and P(gain > 40) is 0.0203
   empirically against 0.0016 under a fitted Normal -- the tail is understated
   thirteenfold. RC1 therefore RESAMPLES per catch and never parameterises.
   The same defect -- a point where a distribution belongs -- has now been
   found three times in this project, and this is the fourth.

`td_layer` had the same shape: a single 0.05 rate supplied by the caller. TD2's
accepted baseline for rec|target is B_pos at rung L4, so the production rate is
per POSITION and comes from the frozen fit.

EVERY NUMBER HERE IS READ, NOT CHOSEN. The shrinkage constant is
`rc1_lib.K_SHRINK`, the pools come from `rc1_sim.pools`, the positional
touchdown rates are aggregated exactly as `run_td2.fit` does, and all of them
are computed on seasons STRICTLY BEFORE the forecast season.
"""
from __future__ import annotations

import collections
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
for _q in (str(_REPO), str(_REPO / 'nfl' / 'research' / 'rc1'),
           str(_REPO / 'nfl' / 'research' / 'td2'),
           str(_REPO / 'nfl' / 'research' / 's2'),
           str(_REPO / 'nfl' / 'research' / 'p4c')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

from sportsplatform.governance.outcome import Outcome, State      # noqa: E402
from nfl.production.nonqb import p4c_params as PP                 # noqa: E402

RECEIVING_SPEC = 'rc1-baseline-frozen-1'
TD_SPEC = 'td2-B_pos-frozen-1'
_CACHE: dict = {}


def _artifacts() -> Outcome:
    a = PP.ensure_artifacts()
    if a.state is not State.PASS:
        return a
    import p4c_build as CB
    CB.P4B = a.value
    return a


def receiving_priors(season: int) -> Outcome:
    """Per-position catch rate and per-catch yardage pool, plus each player's
    own prior history, all from seasons strictly before `season`."""
    key = ('recv', season)
    if key in _CACHE:
        p = _CACHE[key]
        return Outcome.ok('RECEIVING_PRIORS_OK', value=p, cached=True,
                          spec_version=RECEIVING_SPEC, **_recv_ev(p))
    a = _artifacts()
    if a.state is not State.PASS:
        return a
    import rc1_lib as L
    import rc1_sim as S
    _rows, sub = L.load()
    late = [r for r in sub if int(r['season']) >= season]
    if late:
        return Outcome.fail(
            'RECEIVING_FRAME_CARRIES_FORECAST_SEASON',
            f'{len(late)} row(s) from season {season} or later are in the RC1 '
            f'frame; pools() would train on them. Refused, not filtered.',
            n=len(late))
    L.attach_prior(sub)
    pT, pV, prate = S.pools(sub, season)
    own = {}
    for r in sub:
        pid = r['gsis_id']
        cur = own.get(pid)
        if cur is None or r['ord'] > cur['ord']:
            own[pid] = {'ord': r['ord'], 'h_n': r['h_n'],
                        'h_tgt': r['h_tgt'], 'h_rec': r['h_rec'],
                        'h_V_flat': list(r.get('h_V_flat') or []),
                        'position': r['position']}
    # The last row per player carries his history BEFORE that game; his own
    # last game must be folded in or the newest game is silently dropped.
    for r in sub:
        d = own.get(r['gsis_id'])
        if d is not None and r['ord'] == d['ord'] and r['appeared']:
            d['h_n'] += 1
            d['h_tgt'] += r['T']
            d['h_rec'] += r['R']
            d['h_V_flat'] = d['h_V_flat'] + list(r.get('rec_yards_list') or [])
    if not prate:
        return Outcome.fail('RECEIVING_POOLS_EMPTY',
                            'the RC1 positional pools are empty')
    p = {'pos_catch_rate': dict(prate),
         'pos_yardage_pool': {k: np.asarray(v, float) for k, v in pV.items()},
         'own': own, 'k_shrink': float(L.K_SHRINK),
         'trained_on_seasons_before': season}
    _CACHE[key] = p
    return Outcome.ok('RECEIVING_PRIORS_OK', value=p, cached=False,
                      spec_version=RECEIVING_SPEC, **_recv_ev(p))


def _recv_ev(p):
    return {'pos_catch_rate': {k: round(v, 6)
                               for k, v in p['pos_catch_rate'].items()},
            'n_yardage_pool': {k: int(len(v))
                               for k, v in p['pos_yardage_pool'].items()},
            'n_players_with_history': len(p['own']),
            'k_shrink': p['k_shrink'],
            'trained_on_seasons_before': p['trained_on_seasons_before']}


def td_priors(season: int, kind: str = 'rec') -> Outcome:
    """TD2 B_pos: touchdowns per opportunity by position, seasons < season."""
    key = ('td', season, kind)
    if key in _CACHE:
        p = _CACHE[key]
        return Outcome.ok('TD_PRIORS_OK', value=p, cached=True,
                          spec_version=TD_SPEC, **_td_ev(p))
    a = _artifacts()
    if a.state is not State.PASS:
        return a
    import td2_lib as T
    opp, td = (('targets', 'rec_td') if kind == 'rec'
               else ('carries', 'rush_td'))
    rs = T.load(kind, opp, td)
    tr = [r for r in rs if int(r['season']) < season and T.eligible(r)]
    if not tr:
        return Outcome.fail(
            'TD_FRAME_EMPTY',
            f'no eligible TD2 row earlier than {season}; a rate estimated on '
            f'nothing is not the accepted baseline')
    league = [0, 0]
    pos = collections.defaultdict(lambda: [0, 0])
    for r in tr:
        league[0] += r['n_td']; league[1] += r['n_opp']
        pos[r['position']][0] += r['n_td']
        pos[r['position']][1] += r['n_opp']
    p = {'B_league': league[0] / league[1] if league[1] else 0.0,
         'B_pos': {k: (v[0] / v[1] if v[1] else 0.0) for k, v in pos.items()},
         'n_opportunities': {k: int(v[1]) for k, v in pos.items()},
         'n_td': {k: int(v[0]) for k, v in pos.items()},
         'kind': kind, 'trained_on_seasons_before': season,
         'baseline': 'B_pos'}
    _CACHE[key] = p
    return Outcome.ok('TD_PRIORS_OK', value=p, cached=False,
                      spec_version=TD_SPEC, **_td_ev(p))


def _td_ev(p):
    return {'baseline': p['baseline'], 'kind': p['kind'],
            'B_league': round(p['B_league'], 6),
            'B_pos': {k: round(v, 6) for k, v in p['B_pos'].items()},
            'n_opportunities': p['n_opportunities'], 'n_td': p['n_td'],
            'trained_on_seasons_before': p['trained_on_seasons_before']}


def cache_clear():
    _CACHE.clear()
