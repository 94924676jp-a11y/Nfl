#!/usr/bin/env python3.12
"""SHADOW, DEFAULT OFF: DST and kicker DraftKings points as an exact function of integer per-world events.

NOTHING IN PRODUCTION CALLS THIS MODULE (DST/K scoring audit, 2026-10-09; owner ruling the same day that the
event-consistent-worlds repair, nfl/sim/event_consistent_worlds.py, is NOT promoted). `ENABLED` is False and no
production module imports this file; the test nfl/tests/test_dst_k_event_scoring.py asserts both.

THE DEFECT IT ANSWERS. The incumbent's raw DST draw (nfl/sim/dst.py DstModel.draw_components, called from
nfl/sim/game.py simulate_game) is already an integer: a points-allowed tier plus integer historical tuples. The
non-integers are created AFTER scoring, by the multiplicative mean anchor
`classic_slate_run.anchor_means` (out[k] = [x * f for x in v]) applied to DST draws in
nfl/tools/showdown_slate_run.py and nfl/tools/classic_slate_run.py. A DK score times 0.5085 is not a DK score.

WHAT THIS KEEPS FROM THE INCUMBENT, UNCHANGED: every club score (the simulator's continuous world points), every
skill-player draw and stat line (including each quarterback's per-world interceptions from the efficiency step),
and every kicker draw. It replaces ONLY the DST draw, and only by rebuilding it from integer events:

  points allowed   the OPPONENT's simulated club points in the same world, rounded half-down to an integer --
                   the convention nfl/tools/dst_model.pa_expectation already uses for the DST projection
                   (a value within 0.5 of a bucket edge belongs to that bucket; an exact .5 goes to the lower one)
  interceptions    the sum of the OPPOSING quarterbacks' simulated interceptions in that world (exact identity)
  sacks            NegBin(mean = club rate x band ratio, k measured after the band)        [k from history]
  fumble recov.    Poisson(club rate x band ratio)
  def/return TD    Poisson(club rate x band ratio)
  safeties         Poisson(club rate x band ratio)
  blocked kicks    Poisson(club rate x band ratio)
  2-pt returns     not drawn (the DST projection does not model them either; 0.0018 per club-game in history)

  club rate   = the DST projection row's own event item / its DK weight (nfl/tools/dst_model.project), so the
                rates are the club-specific ones the projection already carries
  band ratio  = E[component | points-allowed band] / E[component], measured 2021-2025 by
                nfl/research/dst_scoring/history.py (bands are nfl/sim/dst.py CONDITIONING_BANDS), which keeps
                the measured dependence of sacks and takeaways on the opponent's score that the incumbent's
                tuples carried
  DK points   = nfl/product/dk_scoring.dst_points(...) of those integers, per world. Nothing else.

MEAN, DECLARED NOT DECIDED (owner decision). Two arms, same events, same seed:
  EVENTS      the DST mean is whatever the events give. It will differ from the DST projection, because the
              projection integrates points allowed over a league residual spread (sd 9.9) around the opponent's
              implied total, while the worlds carry the simulator's own opponent score distribution, and because
              interceptions follow the opposing QB's simulated rate rather than the defence's own.
  PROJECTION  one non-negative multiplier m on the FREE components' rates (sacks, fumble recoveries, TDs,
              safeties, blocked kicks) is solved in closed form so that the expected DST mean equals the
              projection's dk_points. Points allowed and interceptions are never moved -- they are identities with
              other players' worlds. If the projection is below what points allowed and interceptions alone give,
              m is 0 and the shortfall is REPORTED (PROJECTION_MEAN_UNREACHABLE), never forced.

KICKERS. The incumbent kicker draw (nfl/tools/kicker_world.draw inside the same worlds) is already an integer DK
score from integer components; `kicker_dk_from_components` re-scores those components through
dk_scoring.kicker_points so the identity is checked by the platform adapter rather than by kicker_world's own
arithmetic. The only kicker defect found is the classic run's anchor step, which would rescale a kicker if a
classic projection ever carried one (classic DK has no K, so no published classic kicker exists today).
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.product import dk_scoring as DK  # noqa: E402

SPEC_VERSION = 'dst-k-event-scoring-shadow-1'
#: DEFAULT OFF. Nothing in production reads this flag, and nothing in production imports this module.
ENABLED = False
PARAMS = _REPO / 'nfl/research/dst_scoring/DST_K_HISTORY_2021_2025.json'

MEAN_EVENTS = 'EVENTS'
MEAN_PROJECTION = 'PROJECTION'

#: Free components: drawn here, rate-scaled under the PROJECTION arm. Name -> (projection event_items key, DK weight).
FREE = {'sacks': ('sack', DK.DST_SACK), 'fumble_recoveries': ('fumble_recovery', DK.DST_FUMBLE_RECOVERY),
        'tds': ('return_td', DK.DST_TD), 'safeties': ('safety', DK.DST_SAFETY),
        'blocked_kicks': ('blocked_kick', DK.DST_BLOCKED_KICK)}
#: DK kicker band names (dk_scoring.BAND_POINTS) for kicker_world's bands.
KICKER_BANDS = {'fg_0_39': 'FG30s', 'fg_40_49': 'FG40s', 'fg_50_plus': 'FG50+'}


class ShadowRefused(RuntimeError):
    """A named refusal: an input the scorer cannot use is never read as zero."""


def load_params(path=PARAMS) -> dict:
    p = pathlib.Path(path)
    if not p.exists():
        raise ShadowRefused(f'DST_K_PARAMS_ABSENT: {p} (build with nfl/research/dst_scoring/history.py)')
    doc = json.loads(p.read_text())
    bands = []
    for key, v in doc['bands_rule_A'].items():
        lo, hi = (int(x) for x in key.split('-'))
        bands.append((lo, hi, {c: float(v['ratio_to_all'][c] or 0.0) for c in FREE}))
    bands.sort()
    disp = doc['dispersion_within_club_season']
    if not bands or any(c not in disp for c in FREE):
        raise ShadowRefused('DST_K_PARAMS_INCOMPLETE: bands or dispersion missing')
    nb_k = {c: (float(disp[c]['nb_k_after_band']) if disp[c]['FAMILY'] == 'NEGATIVE_BINOMIAL' else None)
            for c in FREE}
    return {'bands': bands, 'nb_k': nb_k, 'source': str(p.relative_to(_REPO)) if p.is_relative_to(_REPO) else str(p),
            'spec_version': doc.get('spec_version')}


def points_allowed_integer(points) -> np.ndarray:
    """Opponent club points -> integer points allowed, rounded half-down (dst_model.pa_expectation's convention)."""
    x = np.asarray(points, dtype=float)
    if x.size == 0 or not np.all(np.isfinite(x)):
        raise ShadowRefused('DST_POINTS_ALLOWED_EMPTY_OR_NONFINITE')
    return np.maximum(0, np.ceil(x - 0.5)).astype(np.int64)


def club_rates(proj_row: dict) -> dict:
    """Per-game event rates from the DST projection row's own event items (item / DK weight)."""
    items = ((proj_row or {}).get('dst') or {}).get('event_items') or {}
    out = {}
    for c, (key, w) in FREE.items():
        v = items.get(key)
        if not isinstance(v, (int, float)) or v < 0:
            raise ShadowRefused(f'DST_RATE_MISSING: {proj_row.get("name")}|{proj_row.get("team")} has no '
                                f'event_items[{key!r}]; refused rather than drawn as zero')
        out[c] = float(v) / w
    return out


def _band_ratio(pa_int: np.ndarray, params: dict, comp: str) -> np.ndarray:
    r = np.full(pa_int.shape, np.nan)
    for lo, hi, ratios in params['bands']:
        m = (pa_int >= lo) & (pa_int < hi)
        r[m] = ratios[comp]
    if np.isnan(r).any():
        raise ShadowRefused('DST_BAND_UNCOVERED: a points-allowed value fell outside every measured band')
    return r


def _tier(pa_int: np.ndarray) -> np.ndarray:
    return np.array([DK.dst_points(points_allowed=int(p)) for p in pa_int], dtype=float)


def dst_event_worlds(opp_points, opp_qb_ints, proj_row: dict, params: dict, seed: int,
                     mean_mode: str = MEAN_EVENTS) -> dict:
    """Integer DST events and DK points for every world. Returns components, dk, and an account."""
    if mean_mode not in (MEAN_EVENTS, MEAN_PROJECTION):
        raise ShadowRefused(f'DST_MEAN_MODE_UNKNOWN: {mean_mode!r}')
    pa = points_allowed_integer(opp_points)
    n = pa.size
    ints = np.asarray(opp_qb_ints, dtype=float)
    if ints.shape != (n,):
        raise ShadowRefused(f'DST_INTS_SHAPE: {ints.shape} vs {n} worlds')
    if np.any(ints < 0) or np.any(np.abs(ints - np.round(ints)) > 0):
        raise ShadowRefused('DST_INTS_NOT_NONNEGATIVE_INTEGERS')
    ints = ints.astype(np.int64)
    rates = club_rates(proj_row)
    lam = {c: rates[c] * _band_ratio(pa, params, c) for c in FREE}
    tier = _tier(pa)
    fixed_mean = float(tier.mean() + DK.DST_INTERCEPTION * ints.mean())
    free_mean_at_1 = float(sum(FREE[c][1] * lam[c].mean() for c in FREE))
    target = (proj_row or {}).get('dk_points')
    m, state = 1.0, 'EVENTS_MEAN'
    if mean_mode == MEAN_PROJECTION:
        if not isinstance(target, (int, float)):
            raise ShadowRefused('DST_PROJECTION_MEAN_ABSENT: the PROJECTION arm needs the row dk_points')
        if free_mean_at_1 <= 0:
            raise ShadowRefused('DST_FREE_COMPONENTS_ZERO: no free rate to scale')
        m = (float(target) - fixed_mean) / free_mean_at_1
        state = 'PROJECTION_MEAN_REACHED'
        if m < 0:
            m, state = 0.0, 'PROJECTION_MEAN_UNREACHABLE'
    rng = np.random.default_rng(seed)
    comp = {'points_allowed': pa, 'ints': ints}
    for c in FREE:
        mu = lam[c] * m
        k = params['nb_k'].get(c)
        if k:
            # gamma-Poisson: NegBin with mean mu and variance mu + mu^2 / k
            g = rng.gamma(shape=k, scale=np.where(mu > 0, mu / k, 0.0))
            comp[c] = rng.poisson(g).astype(np.int64)
        else:
            comp[c] = rng.poisson(mu).astype(np.int64)
    dk = np.array([DK.dst_points(points_allowed=int(comp['points_allowed'][w]), sacks=int(comp['sacks'][w]),
                                 ints=int(comp['ints'][w]), fumble_recoveries=int(comp['fumble_recoveries'][w]),
                                 tds=int(comp['tds'][w]), safeties=int(comp['safeties'][w]),
                                 blocked_kicks=int(comp['blocked_kicks'][w])) for w in range(n)], dtype=float)
    acct = {'mean_mode': mean_mode, 'state': state, 'multiplier_on_free_rates': round(m, 5),
            'club_rates': {c: round(v, 5) for c, v in rates.items()},
            'expected_tier_points': round(float(tier.mean()), 4),
            'expected_int_points': round(float(DK.DST_INTERCEPTION * ints.mean()), 4),
            'expected_free_points_at_m1': round(free_mean_at_1, 4),
            'expected_mean': round(fixed_mean + m * free_mean_at_1, 4),
            'projection_dk_points': target,
            'projection_int_rate_of_this_defence': round(rates_int(proj_row), 5),
            'world_int_rate_from_opposing_qbs': round(float(ints.mean()), 5),
            'shortfall_if_unreachable': (round(float(target) - fixed_mean, 4)
                                         if state == 'PROJECTION_MEAN_UNREACHABLE' else None),
            'seed': seed, 'params': params.get('source')}
    return {'components': comp, 'dk': dk, 'account': acct}


def rates_int(proj_row: dict) -> float:
    v = (((proj_row or {}).get('dst') or {}).get('event_items') or {}).get('interception')
    return float(v) / DK.DST_INTERCEPTION if isinstance(v, (int, float)) else float('nan')


def dst_dk_from_components(comp: dict) -> np.ndarray:
    """Re-score stored components through the platform adapter (the identity the tests check)."""
    n = len(comp['points_allowed'])
    return np.array([DK.dst_points(points_allowed=int(comp['points_allowed'][w]), sacks=int(comp['sacks'][w]),
                                   ints=int(comp['ints'][w]), fumble_recoveries=int(comp['fumble_recoveries'][w]),
                                   tds=int(comp['tds'][w]), safeties=int(comp['safeties'][w]),
                                   blocked_kicks=int(comp['blocked_kicks'][w])) for w in range(n)], dtype=float)


def kicker_dk_from_components(band_made: dict, xp_made) -> np.ndarray:
    """kicker_world components ({'fg_0_39': [...], ...}, xp made) -> DK points through dk_scoring.kicker_points."""
    unknown = set(band_made) - set(KICKER_BANDS)
    if unknown:
        raise ShadowRefused(f'KICKER_BAND_UNKNOWN: {sorted(unknown)}')
    return DK.kicker_points({KICKER_BANDS[b]: np.asarray(v, dtype=float) for b, v in band_made.items()},
                            np.asarray(xp_made, dtype=float))


def is_integer_array(x) -> bool:
    a = np.asarray(x, dtype=float)
    return bool(a.size) and bool(np.all(np.isfinite(a))) and bool(np.all(a == np.round(a)))


#: The values a DK DST score can take are all integers >= -4 (the 35+ tier with no event); a kicker score is a
#: non-negative integer under rule A (a miss scores 0).
def valid_dst_values(x) -> bool:
    a = np.asarray(x, dtype=float)
    return is_integer_array(a) and bool(np.all(a >= -4))


def valid_kicker_values(x) -> bool:
    a = np.asarray(x, dtype=float)
    return is_integer_array(a) and bool(np.all(a >= 0))
