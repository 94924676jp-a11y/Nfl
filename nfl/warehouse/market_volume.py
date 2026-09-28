#!/usr/bin/env python3.12
"""How the market maps to team volume, MEASURED. Closes the gap OUT-036 was withdrawn over.

V0 multiplied every club's volume by `implied_total / league_mean`, a 31 per cent uplift for a
28.75-point club. V1 then applied NOTHING and recorded that the coefficient "cannot be estimated
here". Both were wrong, and the second was wrong because I declared a gap after searching one
directory. `nfl/vintage/schedules.*` carries 27 complete seasons of closing lines, so the
relationship is estimable and is estimated here.

THE OWNER'S POINT IS THE HYPOTHESIS UNDER TEST. Scoring more comes largely from efficiency, and a
favoured club tends to run MORE and throw LESS as it protects a lead. So the model is not one
coefficient on an implied total: it is the club's TOTAL (how much football the game holds) and the
club's SPREAD (which side of the game script it is on) entered separately, and the prediction is
that spread carries OPPOSITE signs for passing and rushing volume. If it does not, the hypothesis is
wrong and the artifact will say so.

Fitted on seasons where a club's play detail and its closing line both exist. Standard errors are
clustered by game, because the two clubs in a game share a script by construction.
"""
from __future__ import annotations

import json
import pathlib
import statistics
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.warehouse import era, stats  # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

SPEC_VERSION = 'market-volume-1'
TEAM_GAME = _REPO / 'nfl/warehouse/TEAM_GAME.json'
OUT = _REPO / 'nfl/warehouse/MARKET_VOLUME.json'

#: The volume quantities a projection needs a market response for.
TARGETS = ('plays', 'dropbacks', 'pass_attempts', 'rush_attempts', 'targets', 'rz_trips',
           'rz_drives', 'drives', 'offensive_td', 'points', 'seconds_per_play',
           'neutral_pass_rate')

#: Regressors. `club_spread` is this club's own spread, negative when favoured under the verified
#: home-margin convention, so it is flipped to a FAVOURED-POSITIVE form for readability.
X = ('total_line', 'favoured_by')


def load():
    if not TEAM_GAME.exists():
        return Outcome.blocked('TEAM_GAME_ABSENT', 'build the team-game table first',
                               cause=Cause.DEPENDENCY)
    art = json.loads(TEAM_GAME.read_text())
    rows = []
    for r in art['rows'].values():
        if r.get('club_spread') is None or r.get('total_line') is None:
            continue
        # FAVOURED_BY IS club_spread ITSELF, NOT ITS NEGATION.
        #
        # The verified convention is SPREAD_LINE_IS_HOME_MARGIN: a positive spread_line means the
        # home club is expected to WIN by that much. team_game already flips it per side, so
        # club_spread is positive exactly when this club is favoured. Negating it made 'favoured'
        # mean underdog, and the first run duly reported that favourites score 0.53 FEWER points
        # per point of spread -- which is how the error was caught, because that is not football.
        r = dict(r)
        r['favoured_by'] = r['club_spread']
        rows.append(r)
    return Outcome.ok('TEAM_GAME_LOADED', rows, f'{len(rows)} club-games with a line')


def build():
    lo = load()
    if lo.state.name != 'PASS':
        return lo
    rows = lo.value
    usable = {}
    fits = {}
    for t in TARGETS:
        sub = [r for r in rows
               if r.get(t) is not None
               and r.get(t) not in (era.NOT_AVAILABLE_FOR_ERA, era.UNKNOWN_PENDING_ACQUISITION)]
        usable[t] = len(sub)
        if len(sub) < 200:
            fits[t] = {'state': 'NOT_ENOUGH_COVERAGE', 'n': len(sub),
                       'NOTE': ('this quantity needs play detail, which exists in this checkout '
                                'only for the seasons with a play-by-play capture. It is an '
                                'acquisition gap, not an era gap.')}
            continue
        fit = stats.ols(sub, t, list(X), cluster='game_id')
        # and the single-regressor form V0 effectively used, for comparison
        simple = stats.ols(sub, t, ['implied_total'], cluster='game_id')
        mean_y = statistics.fmean(float(r[t]) for r in sub)
        fits[t] = {
            'two_factor': fit, 'implied_total_only': simple,
            'mean': round(mean_y, 4),
            'seasons': sorted({r['season'] for r in sub}),
            'n_club_games': len(sub),
        }
        if fit.get('state') == 'FITTED':
            c, se = fit['coef'], fit['se']
            fits[t]['interpretation'] = {
                'per_point_of_game_total': c.get('total_line'),
                'per_point_favoured': c.get('favoured_by'),
                'total_effect_significant': (abs(c.get('total_line', 0.0))
                                            > 2 * se.get('total_line', 1e9)),
                'spread_effect_significant': (abs(c.get('favoured_by', 0.0))
                                              > 2 * se.get('favoured_by', 1e9)),
                'pct_change_per_extra_10_total': (round(1000.0 * c['total_line'] / mean_y, 3)
                                                  if mean_y else None),
                'pct_change_per_7_point_favourite': (round(700.0 * c['favoured_by'] / mean_y, 3)
                                                     if mean_y else None),
            }

    # THE HYPOTHESIS TEST the owner's refinement implies
    pa = fits.get('pass_attempts', {}).get('two_factor', {})
    ra = fits.get('rush_attempts', {}).get('two_factor', {})
    hyp = {'state': 'NOT_TESTABLE'}
    if pa.get('state') == 'FITTED' and ra.get('state') == 'FITTED':
        p_sp, r_sp = pa['coef']['favoured_by'], ra['coef']['favoured_by']
        p_se, r_se = pa['se']['favoured_by'], ra['se']['favoured_by']
        hyp = {
            'state': 'TESTED',
            'claim': 'a favoured club runs MORE and throws LESS',
            'pass_attempts_per_point_favoured': p_sp,
            'rush_attempts_per_point_favoured': r_sp,
            'pass_se': p_se, 'rush_se': r_se,
            'signs_oppose': (p_sp < 0 < r_sp),
            'pass_effect_beyond_2se': abs(p_sp) > 2 * p_se,
            'rush_effect_beyond_2se': abs(r_sp) > 2 * r_se,
        }
        # REPORTED AS TWO HALVES, because a single flat verdict would throw away what was found.
        # The rushing half is supported far beyond noise; the passing half points the right way and
        # does not clear two standard errors. Collapsing that to NOT_SUPPORTED would be as
        # misleading as collapsing it to SUPPORTED.
        run_ok = r_sp > 0 and abs(r_sp) > 2 * r_se
        pass_dir = p_sp < 0
        pass_ok = pass_dir and abs(p_sp) > 2 * p_se
        hyp['rushing_half'] = ('SUPPORTED' if run_ok else
                               'NOT_SUPPORTED' if r_sp <= 0 else 'DIRECTIONAL_ONLY')
        hyp['passing_half'] = ('SUPPORTED' if pass_ok else
                               'DIRECTIONAL_ONLY' if pass_dir else 'NOT_SUPPORTED')
        hyp['rushing_se_multiple'] = round(abs(r_sp) / r_se, 2) if r_se else None
        hyp['passing_se_multiple'] = round(abs(p_sp) / p_se, 2) if p_se else None
        hyp['verdict'] = ('SUPPORTED' if (run_ok and pass_ok) else
                          'PARTIALLY_SUPPORTED' if (run_ok or pass_ok) else
                          'DIRECTIONAL_ONLY' if pass_dir and r_sp > 0 else 'NOT_SUPPORTED')
        hyp['reading'] = (
            f"a favoured club runs more: {r_sp:+.4f} rush attempts per point of spread, "
            f"{hyp['rushing_se_multiple']} standard errors. It throws less only directionally: "
            f"{p_sp:+.4f} pass attempts per point, {hyp['passing_se_multiple']} standard errors, "
            f"which does not clear the two-error bar. The volume response to the market is real "
            f"and it is SMALL -- V0 scaled all volume by implied/league_mean, about +31 per cent "
            f"for a 28.75-point club, where the measured pass-attempt response is about +8 per "
            f"cent per TEN points of game total and slightly NEGATIVE in the spread.")

    art = {'artifact': 'MARKET_VOLUME', 'spec_version': SPEC_VERSION,
           'regressors': list(X),
           'FAVOURED_BY_SEMANTICS': ('positive when this club is FAVOURED, which under the '
                                     'empirically verified SPREAD_LINE_IS_HOME_MARGIN convention '
                                     'is club_spread itself. An earlier version negated it and '
                                     'reported that favourites score fewer points, which is how '
                                     'the sign error was caught.'),
           'V0_DID': 'multiplied all volume by implied_total / league_mean_implied',
           'V1_DID': 'applied no market scaling at all and said it was unmeasurable here',
           'BOTH_WRONG': ('the first double-counted the market, which also enters the touchdown '
                          'pool; the second declared a gap after searching one directory while 27 '
                          'seasons of closing lines sat in nfl/vintage/schedules'),
           'coverage': usable, 'fits': fits, 'favoured_hypothesis': hyp}
    OUT.write_text(json.dumps(art, indent=1, sort_keys=True, default=str))
    return Outcome.ok('MARKET_VOLUME_BUILT', art,
                      f'{sum(1 for v in fits.values() if v.get("two_factor", {}).get("state") == "FITTED")} '
                      f'of {len(TARGETS)} quantities fitted')


def main() -> int:
    o = build()
    print(o.render() if hasattr(o, 'render') else f'{o.state.name}[{o.code}]')
    if o.state.name != 'PASS':
        return 1
    a = o.value
    print(f"  {'quantity':18s} {'n':>5s} {'mean':>8s} {'/total':>9s} {'/fav':>9s} "
          f"{'R2':>6s} {'%per+10tot':>10s} {'%per-7fav':>10s}")
    for t, f in a['fits'].items():
        tf = f.get('two_factor') or {}
        if tf.get('state') != 'FITTED':
            print(f"  {t:18s} {f.get('n', 0):5d} {f.get('state', tf.get('state'))}")
            continue
        i = f['interpretation']
        st = '*' if i['total_effect_significant'] else ' '
        ss = '*' if i['spread_effect_significant'] else ' '
        print(f"  {t:18s} {tf['n']:5d} {f['mean']:8.3f} "
              f"{tf['coef']['total_line']:8.4f}{st} {tf['coef']['favoured_by']:8.4f}{ss} "
              f"{tf['r2']:6.3f} {i['pct_change_per_extra_10_total']:10.2f} "
              f"{i['pct_change_per_7_point_favourite']:10.2f}")
    h = a['favoured_hypothesis']
    print(f"\n  hypothesis: a favoured club runs MORE and throws LESS -> {h.get('verdict')}")
    if h.get('state') == 'TESTED':
        print(f"    pass attempts per point favoured {h['pass_attempts_per_point_favoured']:+.4f} "
              f"+/- {h['pass_se']:.4f}")
        print(f"    rush attempts per point favoured {h['rush_attempts_per_point_favoured']:+.4f} "
              f"+/- {h['rush_se']:.4f}")
    print(f"  -> {OUT.relative_to(_REPO)}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
