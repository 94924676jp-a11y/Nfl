#!/usr/bin/env python3.12
"""Apply the MEASURED market-to-volume response, as a deviation and never as a level.

THE FORM MATTERS MORE THAN THE COEFFICIENT. A club's baseline volume is already measured from its
own recent games, and those games had their own totals and spreads. Multiplying that baseline by
anything derived from this week's market counts the market twice -- which is what V0 did, scaling all
volume by implied_total / league_mean for a 31 per cent uplift on a 28.75-point club.

So the response is applied to the DEVIATION: how this week's market differs from the market the
baseline was measured under.

    adjusted = baseline
             + b_total * (this_total_line   - mean_total_line_over_baseline_games)
             + b_fav   * (this_favoured_by  - mean_favoured_by_over_baseline_games)

With this week's market equal to the baseline's average the adjustment is exactly zero, which is the
property that makes it safe. Coefficients come from nfl/warehouse/MARKET_VOLUME.json, fitted over
2,782 club-games with errors clustered by game.

Measured magnitudes, for scale: pass attempts respond about +8 per cent per TEN points of game total
and are slightly NEGATIVE in the spread; rush attempts are the strongest spread response in the
table at +0.187 per point favoured, 7.5 standard errors. The true volume response is a few per cent,
not thirty.
"""
from __future__ import annotations

import json
import pathlib
import statistics
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.warehouse import point_in_time as PIT  # noqa: E402

MARKET = _REPO / 'nfl/warehouse/MARKET_VOLUME.json'
TEAM_GAME = PIT.resolve(_REPO / 'nfl/warehouse/TEAM_GAME.json')   # as of the cutoff in a sealed run

#: Only coefficients that clear two clustered standard errors are applied. A coefficient that does
#: not is reported and NOT used -- applying an effect the data cannot distinguish from zero is how a
#: model acquires confident noise. The passing-spread term is exactly this case at 1.79 errors.
MIN_SE_MULTIPLE = 2.0

#: Cap on the total adjustment, as a fraction of the baseline. DECLARED: the fits have R-squared
#: between 0.02 and 0.16, so the market explains little single-game variance and an extreme line
#: should not be allowed to move a volume projection by an implausible amount. The cap binding is
#: recorded per club so it is never silent.
MAX_ADJUSTMENT_FRACTION = 0.20


def load():
    if not MARKET.exists() or not TEAM_GAME.exists():
        return None
    mv = json.loads(MARKET.read_text())
    tg = json.loads(TEAM_GAME.read_text())
    coef = {}
    for field, f in (mv.get('fits') or {}).items():
        tf = f.get('two_factor') or {}
        if tf.get('state') != 'FITTED':
            continue
        c, se = tf['coef'], tf['se']
        entry = {}
        for reg in ('total_line', 'favoured_by'):
            b, s = c.get(reg), se.get(reg)
            if b is None or not s:
                continue
            mult = abs(b) / s
            entry[reg] = {'beta': b, 'se': s, 'se_multiple': round(mult, 3),
                          'applied': mult >= MIN_SE_MULTIPLE}
        coef[field] = entry
    return {'coef': coef, 'team_game': tg['rows'], 'spec': mv.get('spec_version')}


def club_market(rows, club, season, week):
    """This week's market for a club, and the market its baseline games were played under."""
    this = None
    hist = []
    for r in rows.values():
        if r.get('club') != club:
            continue
        s, w = r.get('season'), r.get('week')
        if s == season and w == week:
            this = r
        elif (s == season and w < week) or s == season - 1:
            if r.get('total_line') is not None and r.get('club_spread') is not None:
                hist.append(r)
    if this is None or not hist:
        return None
    return {
        'this_total_line': this.get('total_line'),
        'this_favoured_by': this.get('club_spread'),
        'baseline_mean_total_line': statistics.fmean(r['total_line'] for r in hist),
        'baseline_mean_favoured_by': statistics.fmean(r['club_spread'] for r in hist),
        'n_baseline_games': len(hist),
    }


def adjust(field, baseline, cm, coef):
    """Return (adjusted, accounting). Never returns a level the market invented on its own."""
    if baseline is None or cm is None or field not in coef:
        return baseline, {'state': 'NOT_ADJUSTED',
                          'reason': ('no market for this club' if cm is None else
                                     f'no fitted response for {field}')}
    if cm['this_total_line'] is None or cm['this_favoured_by'] is None:
        return baseline, {'state': 'NOT_ADJUSTED', 'reason': 'THIS_WEEK_MARKET_UNKNOWN',
                          'NOT_ZERO': 'an unknown line leaves the baseline alone; it does not '
                                      'imply an average line'}
    parts, used, skipped = {}, 0.0, []
    for reg, key, base_key in (('total_line', 'this_total_line', 'baseline_mean_total_line'),
                               ('favoured_by', 'this_favoured_by', 'baseline_mean_favoured_by')):
        e = coef[field].get(reg)
        if not e:
            continue
        dev = cm[key] - cm[base_key]
        contrib = e['beta'] * dev
        parts[reg] = {'deviation': round(dev, 4), 'beta': e['beta'],
                      'se_multiple': e['se_multiple'], 'applied': e['applied'],
                      'contribution': round(contrib, 5)}
        if e['applied']:
            used += contrib
        else:
            skipped.append(reg)
    cap = MAX_ADJUSTMENT_FRACTION * abs(baseline)
    capped = False
    if abs(used) > cap:
        used = cap if used > 0 else -cap
        capped = True
    return max(0.0, baseline + used), {
        'state': 'ADJUSTED', 'baseline': round(baseline, 4),
        'adjustment': round(used, 5), 'adjusted': round(max(0.0, baseline + used), 4),
        'parts': parts, 'coefficients_not_applied_below_2se': skipped,
        'cap_fraction': MAX_ADJUSTMENT_FRACTION, 'cap_binding': capped,
        'n_baseline_games': cm['n_baseline_games'],
        'FORM': ('applied to the DEVIATION of this week market from the market the baseline was '
                 'measured under, so an average line produces exactly zero adjustment. V0 applied '
                 'a multiplier to the level and counted the market twice.'),
    }
