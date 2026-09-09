"""D3 production parameters: the ACCEPTED P4C fit, not a reconstruction.

WHY THIS MODULE EXISTS

The TEST-ONLY engine rehearsal reconstructed `add_pool` and `mass_pool` from
the frozen summary statistics -- a normal draw scaled off mean(sigma_lr). That
is fine for proving wiring and is labelled as such inside it. It is NOT the
accepted mechanism: §D of the R3 packet requires the accepted alpha0,
sigma_lr, sigma_lg, q_zero and the empirical residual pools themselves.

The real fit needs `panel_enriched.pkl`, which is deliberately not committed
because it is byte-for-byte regenerable from the committed leaves. So that is
what this does: regenerate it (25.7s, hash-verified by the regeneration script
itself and re-verified here), then call the FROZEN `p4c_build.prepare_class`
and `p4c_build.fit_params`. No parameter is computed in this file.

CHRONOLOGY. `fit_params(sub, cls, ev, rows_all)` trains on seasons strictly
before `ev`, so a 2026 forecast passes ev=2026 and consumes no 2026 outcome --
there are none. The mass pool additionally excludes 2020 by predeclaration,
and that exclusion lives in the research module, not here.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
for _q in (str(_REPO), str(_REPO / 'nfl' / 'research' / 'p4c')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

from sportsplatform.governance.outcome import (Cause, Outcome,   # noqa: E402
                                               State)
from nfl.production import derived as D                          # noqa: E402

SPEC = _REPO / 'nfl' / 'research' / 'repro' / 'ABC_MPR_IDENTITY.json'
REGEN = _REPO / 'nfl' / 'research' / 'repro' / 'regenerate.py'
SPEC_VERSION = 'p4c-system-C-frozen-params-1'
ARTIFACTS = ('panel_enriched.pkl', 'volume_store.npy')

_CACHE: dict = {}
_DIR = None


def _sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as fh:
        for b in iter(lambda: fh.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def ensure_artifacts(dest=None, timeout=1800) -> Outcome:
    """The verified derived artifacts, READ-ONLY, from production's own cache.

    R3 shelled out to `regenerate.py`'s command line here and then restored the
    one research file it noticed being written. Both halves of that were wrong:
    a forecast should not invoke a mutating research command at all, and the
    restore missed the 138 MB of derived artifacts the builders were writing
    through symlinks into nfl/research/p4b. `nfl.production.derived` does it
    the other way round -- pure functions, a temp work tree, and a cache
    outside the research tree.
    """
    global _DIR
    o = D.artifacts()
    if o.state is State.PASS:
        _DIR = pathlib.Path(o.value)
    return o


def params(cls: str, season: int) -> Outcome:
    """The frozen P4C parameters for `cls`, fitted on seasons < season."""
    key = (cls, season)
    if key in _CACHE:
        p = _CACHE[key]
        return Outcome.ok('P4C_PARAMS_OK', value=p, cached=True,
                          spec_version=SPEC_VERSION, **_ev(p, cls, season))
    a = ensure_artifacts()
    if a.state is not State.PASS:
        return a
    import p4c_build as B
    import p4c_lib as L
    if cls not in L.CLASSES:
        return Outcome.fail('UNKNOWN_CLASS', f'{cls!r} is not a P4C class')
    B.P4B = str(_DIR)
    rows = B.load_panel()
    late = [r for r in rows if int(r['season']) >= season]
    if late:
        return Outcome.fail(
            'P4C_PANEL_CARRIES_FORECAST_SEASON',
            f'{len(late)} panel row(s) are from season {season} or later. '
            f'fit_params would train on them; a forecast-season row in the '
            f'panel is a refusal, never a filter.', n=len(late))
    sub = B.prepare_class(rows, cls)
    par = B.fit_params(sub, cls, season, rows)
    if not par.get('add_pool') or par.get('mass_pool') is None or \
            len(par['mass_pool']) == 0:
        return Outcome.fail(
            'P4C_PARAMS_EMPTY',
            f'the frozen fit produced an empty pool for {cls}; an empty pool '
            f'is not a parameter set')
    _CACHE[key] = par
    return Outcome.ok('P4C_PARAMS_OK', value=par, cached=False,
                      spec_version=SPEC_VERSION, **_ev(par, cls, season))


def _ev(par, cls, season):
    return {
        'alloc_class': cls, 'trained_on_seasons_before': season,
        'n_add_pool': {k: int(len(v)) for k, v in par['add_pool'].items()},
        'n_mass_pool': int(len(par['mass_pool'])),
        'mass_mean': float(par['mass_mean']),
        'mass_pool_seasons': par.get('mass_pool_seasons'),
        'sigma_lr': {k: round(float(v), 6) for k, v in par['sigma_lr'].items()},
        'sigma_lg': {k: round(float(v), 6) for k, v in par['sigma_lg'].items()},
        'q_zero': {k: round(float(v), 6) for k, v in par['q_zero'].items()},
        'alpha0': par.get('alpha0'),
    }


def cache_clear():
    _CACHE.clear()


def class_point_forecast(cls: str, season: int, week: int, players) -> Outcome:
    """`C`, the per-player point forecast of the class share.

    This is `_C` in `p4c_build.fit_params`: the frozen ewma over the player's
    PRIOR APPEARED class shares, falling back to the positional training mean
    when he has none. The ewma is imported from the research module; the
    fallback is the one the research code declares, not a zero.
    """
    a = ensure_artifacts()
    if a.state is not State.PASS:
        return a
    import p4c_build as B
    import p4c_lib as L
    if cls not in L.CLASSES:
        return Outcome.fail('UNKNOWN_CLASS', f'{cls!r} is not a P4C class')
    B.P4B = str(_DIR)
    skey = L.CLASSES[cls]['share']
    cut = season * 100 + week
    key = ('C', cls, cut)
    if key not in _CACHE:
        rows = B.load_panel()
        hist, pri_v = {}, []
        for r in sorted(rows, key=lambda x: (x['ord'], x['team'],
                                             x['gsis_id'])):
            if r['position'] not in L.CLASSES[cls]['pos']:
                continue
            if r['ord'] >= cut:
                continue
            v = r.get(skey)
            if v is None or not r['appeared']:
                continue
            hist.setdefault(r['gsis_id'], []).append(v)
            pri_v.append((r['position'], v))
        pri = {}
        for pos in L.CLASSES[cls]['pos']:
            vals = [v for p_, v in pri_v if p_ == pos]
            if vals:
                pri[pos] = float(np.mean(vals))
        _CACHE[key] = (hist, pri)
    hist, pri = _CACHE[key]
    if not hist:
        return Outcome.fail(
            'CLASS_HISTORY_EMPTY',
            f'no prior appeared {cls} share earlier than {season} week '
            f'{week}; a point forecast over nothing is not one')
    out, fell_back = {}, []
    for q in players:
        pid, pos = q.get('gsis_id'), q.get('position')
        if pos not in L.CLASSES[cls]['pos'] or not pid:
            continue
        h = hist.get(pid)
        v = B.ewma(h) if h else pri.get(pos)
        if v is None:
            return Outcome.fail(
                'CLASS_POINT_FORECAST_UNAVAILABLE',
                f'neither history nor a positional prior exists for {pos}')
        if not h:
            fell_back.append(pid)
        out[pid] = float(v)
    if not out:
        return Outcome.fail(
            'CLASS_POINT_FORECAST_EMPTY',
            f'no {cls}-class player among {len(players)} supplied')
    return Outcome.ok('CLASS_POINT_FORECAST_OK', value=out,
                      spec_version=SPEC_VERSION, alloc_class=cls,
                      n_players=len(out), ordinal_cut=cut,
                      n_on_positional_prior=len(fell_back),
                      positional_prior={k: round(v, 6)
                                        for k, v in pri.items()})
