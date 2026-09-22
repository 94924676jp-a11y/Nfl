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

import collections
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


def class_point_forecast_cs(cls: str, season: int, week: int, players,
                           *, current_season, role_prior=None, tiers=None,
                           role_by_id=None, depth_rank=None,
                           declared_starters=None) -> Outcome:
    """`C` from evidence that INCLUDES the current season. Stage 6, repaired.

    The historical-only `class_point_forecast` below is left exactly as it
    was, so a baseline run remains reproducible and the two can be compared
    under one change. This is the new path and it is selected explicitly by
    the caller supplying `current_season`; there is no implicit switch.
    """
    a = ensure_artifacts()
    if a.state is not State.PASS:
        return a
    import p4c_build as B
    import p4c_lib as L
    if cls not in L.CLASSES:
        return Outcome.fail('UNKNOWN_CLASS', f'{cls!r} is not a P4C class')
    from nfl.production.nonqb import opportunity_centre as OC
    from nfl.production.nonqb import role_prior as RP

    po = OC.load_params(cls)
    if po.state is not State.PASS:
        return po
    B.P4B = str(_DIR)
    panel = B.load_panel()
    cut = season * 100 + week
    skey = L.CLASSES[cls]['share']
    okey = 'carries' if cls == 'carries' else 'targets'

    hist, posvals = collections.defaultdict(list), collections.defaultdict(list)
    for r in panel:
        if r['position'] not in L.CLASSES[cls]['pos'] or r['ord'] >= cut:
            continue
        v = r.get(skey)
        if v is None or not r.get('appeared'):
            continue
        hist[r['gsis_id']].append(OC.Observation(
            season=int(r['season']), week=int(r.get('week') or 0),
            team=r.get('team'), share=float(v),
            opportunity=float(r.get(okey) or 0.0),
            source='historical_panel', ord=r['ord']))
        posvals[r['position']].append(float(v))
    if not hist:
        return Outcome.fail(
            'CLASS_HISTORY_EMPTY',
            f'no prior appeared {cls} share earlier than {season} week '
            f'{week}; a point forecast over nothing is not one')
    posmean = {k: float(np.mean(v)) for k, v in posvals.items()}

    anchor = {}
    if role_prior is not None and tiers is not None:
        for q in players:
            t = (tiers or {}).get(q.get('gsis_id'), RP.MAX_TIER)
            tm = role_prior['tier_mean'].get(
                RP._tier_label(q.get('position'), t))
            if tm is not None:
                anchor[q.get('gsis_id')] = float(tm)
    kk = {k: float(v) for k, v in ((role_prior or {}).get('k') or {}).items()}

    pool = [q for q in players
            if q.get('position') in L.CLASSES[cls]['pos'] and q.get('gsis_id')]
    o = OC.build_centres(
        pool, target=cls, season=season, week=week, params=po.value,
        historical=hist, current_season=current_season,
        role_by_id=role_by_id, depth_anchor_by_id=anchor,
        depth_rank_by_id=depth_rank, positional_mean=posmean,
        shrinkage_k=kk, declared_starters=declared_starters)
    if o.state is not State.PASS:
        return o

    # PARTICIPATION WEIGHTING, unchanged from the historical path: C is a
    # conditional-on-appearing share and E[share] = P(appears) * E[share|app].
    out, weighted = dict(o.value['centre']), []
    for q in pool:
        pp = q.get('participation_prior')
        pid = q.get('gsis_id')
        if pp is not None and pid in out:
            out[pid] = float(out[pid]) * float(pp)
            weighted.append(pid)
    return Outcome.ok(
        'CLASS_POINT_FORECAST_CURRENT_SEASON_OK', value=out,
        spec_version=SPEC_VERSION, alloc_class=cls, n_players=len(out),
        ordinal_cut=cut, stage6='opportunity_centre',
        opportunity_centre_spec=OC.SPEC_VERSION,
        n_participation_weighted=len(weighted),
        n_with_current_season_evidence=o.value[
            'n_with_current_season_evidence'],
        by_basis=o.value['by_basis'],
        stage2_params=o.value['params'],
        attribution={p: a.as_dict()
                     for p, a in o.value['attribution'].items()},
        detail=o.detail)


def class_point_forecast(cls: str, season: int, week: int, players,
                        role_prior=None, tiers=None) -> Outcome:
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
    out, fell_back, weighted = {}, [], []
    for q in players:
        pid, pos = q.get('gsis_id'), q.get('position')
        if pos not in L.CLASSES[cls]['pos'] or not pid:
            continue
        h = hist.get(pid)
        if role_prior is not None:
            # R6. The player's own history shrunk toward his POINT-IN-TIME
            # TIER, instead of a positional mean that treats a team's second
            # option and its ninth as the same player. With a long history the
            # shrinkage weight goes to one and this returns his own value
            # unchanged, so it cannot overwrite an established starter.
            from nfl.production.nonqb import role_prior as RP
            t = (tiers or {}).get(pid, RP.MAX_TIER)
            v = RP.weight(pid, pos, B.ewma(h) if h else None,
                          len(h) if h else 0, t, role_prior)
        else:
            v = B.ewma(h) if h else pri.get(pos)
        if v is None:
            return Outcome.fail(
                'CLASS_POINT_FORECAST_UNAVAILABLE',
                f'neither history nor a positional prior exists for {pos}')
        if not h:
            fell_back.append(pid)
        # C IS A CONDITIONAL-ON-APPEARING SHARE. This module's own defect
        # statement says so: "P4C weights are conditional-on-appearing shares
        # consumed as unconditional weights over an unfiltered roster". R5
        # patched that by hard-filtering the pool to roster status ACT, which
        # works only while an ACT column exists -- and for 2026 week 2 it does
        # not, because the vintage reduction drops it.
        #
        # So the weight becomes what it always should have been:
        #
        #     E[share] = P(appears) * E[share | appears]
        #
        # A player carrying no participation_prior is untouched, so every
        # existing caller and every frozen arm keeps its exact behaviour. Where
        # the prior IS supplied it is uniform across the active pool, so it
        # cancels in the simplex normalisation and active players are scored
        # identically to the hard filter -- what changes is that a
        # practice-squad or reserve player contributes his own small mass
        # instead of a full share or nothing at all.
        pp = q.get('participation_prior')
        if pp is not None:
            v = float(v) * float(pp)
            weighted.append(pid)
        out[pid] = float(v)
    if not out:
        return Outcome.fail(
            'CLASS_POINT_FORECAST_EMPTY',
            f'no {cls}-class player among {len(players)} supplied')
    return Outcome.ok('CLASS_POINT_FORECAST_OK', value=out,
                      spec_version=SPEC_VERSION, alloc_class=cls,
                      n_players=len(out), ordinal_cut=cut,
                      n_on_positional_prior=len(fell_back),
                      n_participation_weighted=len(weighted),
                      role_prior_applied=role_prior is not None,
                      positional_prior={k: round(v, 6)
                                        for k, v in pri.items()})
