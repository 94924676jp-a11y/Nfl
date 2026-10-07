#!/usr/bin/env python3.12
"""Football accounting invariants for simulated (and historical) world bundles.

LAYER: RESEARCH / SHADOW_ONLY. Nothing on the production path imports this module.

A WORLD BUNDLE is the provider-neutral form every stage of every forecaster is converted to before it is checked:

    bundle = {'provider': 'INCUMBENT' | 'EVENT_LINKED' | 'HISTORY', 'stage': str, 'n': int,
              'order': [home, away],
              'clubs': {club: {'ids': [...], 'pos': [...],
                               'S': float array (players, n, len(PF)),        # NaN column = NOT REPRESENTED
                               'team': {field: array(n)}, 'dst': {field: array(n)},
                               'kicker': {field: array(n)}, 'dk': {'core': (P, n), 'classic': (P, n)} | None}},
              'ledger': {club: {column: array(events)}} | None}

`check_bundle` counts, per invariant, how many units (player-worlds, club-worlds or events) violate it. It never
repairs anything. An invariant whose inputs the provider does not represent is reported NOT_REPRESENTED with a
count of None -- never 0, because "not drawn" is not "drawn and correct".

OFFICIAL-STAT CONVENTIONS (declared; each has a fixture test in nfl/tests/test_event_linked_world.py)
  SACK_YARDS        a sack is not a pass attempt; sack yards reduce the TEAM's net passing yards, never the passer's
                    gross passing yards (NFL official convention; DK scores gross passing yards).
  ALL_PASSERS       passing identities are over every player with a pass attempt, not over QBs only, so a trick-play
                    pass by a receiver keeps them exact.
  TWO_POINT         a two-point conversion is a try, not a touchdown, target, carry or reception. It lives on the
                    try ledger (C08). DK's +2 to the converting player is NOT_REPRESENTED (not attributed).
  DK_PA_v1          DraftKings points allowed for the DST of club T = the opponent's points EXCLUDING the opponent's
                    defensive (takeaway-return) touchdowns, the tries that followed them, and the opponent's
                    safeties. Opponent kick/punt-return touchdowns and their tries COUNT. Source: DraftKings rules
                    text as recorded in external-research/.../nfl-full-product-research-packet.pplx.md:344 and the
                    2026W4 standings finding nfl/dfs/salaries/postgame/FINDINGS_2026W4_STANDINGS.md F1.
Exceptions that only HISTORY may claim (the simulators generate none of these plays, so a simulated world may not):
  LATERAL           yards credited to a lateral recipient without a reception / carry (nflverse
                    lateral_receiving_yards / lateral_rushing_yards). Excuses P02, P05, C01.
  OFFENSIVE_FUMBLE_RECOVERY_TD  an offensive touchdown that is neither a passing nor a rushing TD. Excuses C05.
"""
from __future__ import annotations

import collections

import numpy as np

#: Player stat fields, in column order of bundle['clubs'][c]['S'].
PF = ('pass_att', 'completions', 'pass_yards', 'pass_td', 'ints', 'sacks_taken', 'sack_yards', 'carries',
      'rush_yards', 'rush_td', 'targets', 'receptions', 'rec_yards', 'rec_td', 'fumbles_lost')
PX = {f: i for i, f in enumerate(PF)}
COUNT_FIELDS = ('pass_att', 'completions', 'pass_td', 'ints', 'sacks_taken', 'carries', 'rush_td', 'targets',
                'receptions', 'rec_td', 'fumbles_lost')
#: A yardage is "present" above half a yard (official yards are integers; the incumbent's are continuous).
YARD_PRESENCE_TOL = 0.5
#: Equalities between sums of the same quantities (float reassociation only).
EQ_TOL = 1e-6

POINTS_BANDS = ((0, 1, 10.0), (1, 7, 7.0), (7, 14, 4.0), (14, 21, 1.0), (21, 28, 0.0), (28, 35, -1.0),
                (35, 10 ** 9, -4.0))     # == nfl/sim/dst.py POINTS_BANDS (asserted in the tests)
FG_BAND_POINTS = {'fg_0_39': 3.0, 'fg_40_49': 4.0, 'fg_50_plus': 5.0}   # == kicker_world.BAND_POINTS

OFFICIAL_STAT_EXCEPTIONS = {
    'LATERAL': ('P02', 'P05', 'C01'),
    'OFFENSIVE_FUMBLE_RECOVERY_TD': ('C05',),
}


class InvariantError(RuntimeError):
    def __init__(self, code, detail=''):
        super().__init__(f'{code}: {detail}')
        self.code = code


def _require(ok, code, detail=''):
    if not ok:
        raise InvariantError(code, detail)


# ------------------------------------------------------------------------------------------------ registry
INVARIANTS = collections.OrderedDict([
    # player-world scope
    ('P01', ('player', 'receptions <= targets')),
    ('P02', ('player', 'receiving yards require a reception (|rec_yards| > 0.5 => receptions > 0)')),
    ('P03', ('player', 'receiving TDs <= receptions')),
    ('P04', ('player', 'rushing TDs <= carries')),
    ('P05', ('player', 'rushing yards require a carry')),
    ('P06', ('player', 'passing yards require a completion')),
    ('P06W', ('player', 'passing yards require a pass attempt (weak form of P06)')),
    ('P07', ('player', 'passing TDs <= completions')),
    ('P07W', ('player', 'passing TDs <= pass attempts (weak form of P07)')),
    ('P08', ('player', 'completions <= pass attempts')),
    ('P09', ('player', 'interceptions thrown <= incompletions (attempts - completions)')),
    ('P09W', ('player', 'interceptions thrown <= pass attempts (weak form of P09)')),
    ('P10', ('player', 'every count field is a non-negative integer')),
    ('P11', ('player', 'fumbles lost <= carries + receptions + sacks taken')),
    ('P12', ('player', 'sacks taken only by a player with a pass attempt or listed QB; sack yards >= 0')),
    # club-world scope
    ('C01', ('club', 'sum of passing yards (all passers) == sum of receiving yards')),
    ('C02', ('club', 'sum of passing TDs == sum of receiving TDs')),
    ('C03', ('club', 'sum of completions == sum of receptions')),
    ('C04', ('club', 'pass attempts == targets + throwaways')),
    ('C05', ('club', 'offensive TDs == passing TDs + rushing TDs')),
    ('C06', ('club', 'points == 6*(off TD + def TD + return TD) + XP made + 2*2pt made + 3*FG + 2*safeties')),
    ('C07', ('club', 'points are a non-negative integer')),
    ('C08', ('club', 'tries: XP att + 2pt att == all TDs; made <= attempted')),
    ('C09', ('club', 'FG made == sum of FG made by distance band')),
    ('C10', ('club', 'kicker DK == XP made + 3/4/5 per FG by band (DK Showdown/Classic kicker rule, no miss term)')),
    ('C11', ('club', 'team net passing yards == gross passing yards - sack yards; team sacks == sum of sacks taken')),
    ('C12', ('club', 'team volume fields == sums of player fields (pass attempts, carries)')),
    # DST of club T against the offence of its opponent O, club-world scope
    ('D01', ('dst', 'DST interceptions == interceptions thrown by the opponent')),
    ('D01W', ('dst', 'interceptions thrown by the opponent <= DST takeaways (weak form of D01/D03)')),
    ('D02', ('dst', 'DST sacks == sacks taken by the opponent')),
    ('D03', ('dst', 'DST fumble recoveries == fumbles lost by the opponent')),
    ('D04', ('dst', 'DST takeaways == DST interceptions + DST fumble recoveries')),
    ('D05', ('dst', "DST defensive + return TDs == the club's defensive + return TDs on its scoreboard")),
    ('D06', ('dst', "DST safeties == the club's safeties on its scoreboard")),
    ('D07', ('dst', 'DST takeaway-return TDs <= DST takeaways')),
    ('D08', ('dst', 'DST points allowed == DK_PA_v1(opponent scoring events)')),
    ('D09', ('dst', 'DST tier == DK tier(points allowed)')),
    ('D10', ('dst', 'DST DK == tier + sacks + 2*INT + 2*fumble rec + 6*(def + return TD) + 2*safeties')),
    # scored stage
    ('S01', ('player', 'player DK core == DK core of his stat line')),
    ('S02', ('player', 'player DK classic == DK classic of his stat line (bonuses, -1 INT, -1 fumble lost)')),
    # event ledger (EVENT_LINKED only)
    ('E01', ('event', 'a TD flag sits only on a completed pass or a carry, at most one per event')),
    ('E02', ('event', 'an interception sits only on an incomplete pass attempt')),
    ('E03', ('event', 'TD, interception and fumble lost are mutually exclusive on one event')),
    ('E04', ('event', 'yards sit only on completions, carries and sacks; sack yards <= 0')),
    ('E05', ('event', 'aggregating the ledger reproduces every player stat line exactly')),
    ('E06', ('event', 'every pass and sack has a passer with that role; every carry a rusher; every target a receiver')),
])

STAGE_NAMES = ('S0_raw', 'S1_after_efficiency', 'S2_after_dst', 'S3_after_scoring')


# ------------------------------------------------------------------------------------------------ scoring rules
def dk_tier(pa):
    """DraftKings points-allowed tier, vectorised (nfl/sim/dst.tier)."""
    p = np.maximum(0.0, np.asarray(pa, float))
    out = np.full(p.shape, -4.0)
    for lo, hi, v in POINTS_BANDS[::-1]:
        out = np.where((p >= lo) & (p < hi), v, out)
    return out


def dk_core(S):
    """DK core (the SC-COH-1 pre-registered player score): no bonuses, no INT or fumble term."""
    g = lambda f: S[..., PX[f]]
    return (0.04 * g('pass_yards') + 4 * g('pass_td') + 0.1 * g('rush_yards') + 6 * g('rush_td')
            + 0.1 * g('rec_yards') + g('receptions') + 6 * g('rec_td'))


def dk_classic(S):
    """DraftKings Classic: classic_slate_run.dk_from_stats (bonuses, -1 per INT) minus 1 per fumble lost.
    Two-point conversions (+2) are NOT_REPRESENTED (not attributed to a player)."""
    g = lambda f: np.nan_to_num(S[..., PX[f]], nan=0.0)
    pyd, ryd, recyd = g('pass_yards'), g('rush_yards'), g('rec_yards')
    return (pyd * 0.04 + g('pass_td') * 4.0 + np.where(pyd >= 300, 3.0, 0.0) - g('ints')
            + ryd * 0.1 + g('rush_td') * 6.0 + np.where(ryd >= 100, 3.0, 0.0)
            + g('receptions') * 1.0 + recyd * 0.1 + g('rec_td') * 6.0 + np.where(recyd >= 100, 3.0, 0.0)
            - g('fumbles_lost'))


# ------------------------------------------------------------------------------------------------ helpers
def _has(arr):
    if arr is None:
        return False
    a = np.asarray(arr, float)
    return a.size > 0 and not np.all(np.isnan(a))


def _col(S, f):
    return S[..., PX[f]]


def _rep(S, *fields):
    return all(_has(_col(S, f)) for f in fields)


def _get(d, k):
    v = (d or {}).get(k)
    return None if v is None or not _has(v) else np.asarray(v, float)


def validate_bundle(bundle):
    _require(isinstance(bundle, dict), 'INV_NOT_A_BUNDLE', type(bundle).__name__)
    n = bundle.get('n')
    _require(isinstance(n, int) and n > 0, 'INV_EMPTY_BUNDLE', f'n = {n!r}')
    clubs = bundle.get('clubs') or {}
    order = bundle.get('order') or []
    _require(len(order) == 2 and set(order) == set(clubs), 'INV_EMPTY_BUNDLE', f'order {order} clubs {list(clubs)}')
    for c in order:
        cb = clubs[c]
        S = np.asarray(cb.get('S'), float)
        _require(S.ndim == 3 and S.shape[0] > 0 and S.shape[1] == n and S.shape[2] == len(PF),
                 'INV_EMPTY_BUNDLE', f'{c}: S shape {S.shape}, want (players>0, {n}, {len(PF)})')
        _require(len(cb.get('ids') or []) == S.shape[0] == len(cb.get('pos') or []), 'INV_EMPTY_BUNDLE',
                 f'{c}: ids / pos / S disagree')
        for k in ('team', 'dst'):
            _require(isinstance(cb.get(k), dict) and cb[k], 'INV_EMPTY_BUNDLE', f'{c}: no {k} block')
    return n


# ------------------------------------------------------------------------------------------------ the checker
def check_bundle(bundle, exceptions=None) -> dict:
    """{invariant id: {'state': CHECKED | NOT_REPRESENTED, 'violations': int | None, 'units': int}}."""
    n = validate_bundle(bundle)
    prov = bundle.get('provider')
    if exceptions:
        _require(prov == 'HISTORY', 'INV_EXCEPTION_NOT_ALLOWED_FOR_SIMULATION',
                 f'provider {prov!r} may not claim an official-stat exception; only HISTORY plays contain laterals')
        for c, kinds in exceptions.items():
            for k in kinds:
                _require(k in OFFICIAL_STAT_EXCEPTIONS, 'INV_UNKNOWN_EXCEPTION', k)
    out = {k: {'state': 'NOT_REPRESENTED', 'violations': None, 'units': 0} for k in INVARIANTS}

    def excused(inv, club):
        m = np.zeros(n, bool)
        for kind, mask in ((exceptions or {}).get(club) or {}).items():
            if inv in OFFICIAL_STAT_EXCEPTIONS[kind]:
                m |= np.asarray(mask, bool)
        return m

    def add(inv, viol, club, scope_shape):
        """viol: boolean array (n,) or (P, n)."""
        v = np.asarray(viol, bool)
        ex = excused(inv, club)
        v = v & ~ex if v.ndim == 1 else v & ~ex[None, :]
        r = out[inv]
        r['state'] = 'CHECKED'
        r['violations'] = (r['violations'] or 0) + int(v.sum())
        r['units'] += int(np.prod(scope_shape))

    order = bundle['order']
    for c in order:
        o = order[1] if c == order[0] else order[0]
        cb, ob = bundle['clubs'][c], bundle['clubs'][o]
        S = np.asarray(cb['S'], float)
        P_ = S.shape[0]
        pos = np.array(cb['pos'])
        shp = (P_, n)
        T = cb['team']
        # ---------------------------------------------------------------- player
        if _rep(S, 'receptions', 'targets'):
            add('P01', _col(S, 'receptions') > _col(S, 'targets'), c, shp)
        if _rep(S, 'receptions', 'rec_yards'):
            add('P02', (np.abs(_col(S, 'rec_yards')) > YARD_PRESENCE_TOL) & (_col(S, 'receptions') == 0), c, shp)
        if _rep(S, 'receptions', 'rec_td'):
            add('P03', _col(S, 'rec_td') > _col(S, 'receptions'), c, shp)
        if _rep(S, 'carries', 'rush_td'):
            add('P04', _col(S, 'rush_td') > _col(S, 'carries'), c, shp)
        if _rep(S, 'carries', 'rush_yards'):
            add('P05', (np.abs(_col(S, 'rush_yards')) > YARD_PRESENCE_TOL) & (_col(S, 'carries') == 0), c, shp)
        if _rep(S, 'completions', 'pass_yards'):
            add('P06', (np.abs(_col(S, 'pass_yards')) > YARD_PRESENCE_TOL) & (_col(S, 'completions') == 0), c, shp)
        if _rep(S, 'pass_att', 'pass_yards'):
            add('P06W', (np.abs(_col(S, 'pass_yards')) > YARD_PRESENCE_TOL) & (_col(S, 'pass_att') == 0), c, shp)
        if _rep(S, 'completions', 'pass_td'):
            add('P07', _col(S, 'pass_td') > _col(S, 'completions'), c, shp)
        if _rep(S, 'pass_att', 'pass_td'):
            add('P07W', _col(S, 'pass_td') > _col(S, 'pass_att'), c, shp)
        if _rep(S, 'completions', 'pass_att'):
            add('P08', _col(S, 'completions') > _col(S, 'pass_att'), c, shp)
        if _rep(S, 'completions', 'pass_att', 'ints'):
            add('P09', _col(S, 'ints') > _col(S, 'pass_att') - _col(S, 'completions'), c, shp)
        if _rep(S, 'pass_att', 'ints'):
            add('P09W', _col(S, 'ints') > _col(S, 'pass_att'), c, shp)
        bad = np.zeros(shp, bool)
        for f in COUNT_FIELDS:
            x = _col(S, f)
            if _has(x):
                xx = np.nan_to_num(x, nan=0.0)
                bad |= (xx < 0) | (np.abs(xx - np.round(xx)) > 1e-9)
        add('P10', bad, c, shp)
        if _rep(S, 'fumbles_lost', 'carries', 'receptions', 'sacks_taken'):
            add('P11', _col(S, 'fumbles_lost') > _col(S, 'carries') + _col(S, 'receptions') + _col(S, 'sacks_taken'),
                c, shp)
        if _rep(S, 'sacks_taken', 'sack_yards'):
            role = (pos == 'QB')[:, None] | (_col(S, 'pass_att') > 0)
            add('P12', ((_col(S, 'sacks_taken') > 0) & ~role) | (_col(S, 'sack_yards') < -EQ_TOL), c, shp)
        # ---------------------------------------------------------------- club
        if _rep(S, 'pass_yards', 'rec_yards'):
            add('C01', np.abs(np.nansum(_col(S, 'pass_yards'), 0) - np.nansum(_col(S, 'rec_yards'), 0)) > EQ_TOL, c, (n,))
        if _rep(S, 'pass_td', 'rec_td'):
            add('C02', np.nansum(_col(S, 'pass_td'), 0) != np.nansum(_col(S, 'rec_td'), 0), c, (n,))
        if _rep(S, 'completions', 'receptions'):
            add('C03', np.nansum(_col(S, 'completions'), 0) != np.nansum(_col(S, 'receptions'), 0), c, (n,))
        thr = _get(T, 'throwaways')
        if thr is not None and _rep(S, 'pass_att', 'targets'):
            add('C04', np.nansum(_col(S, 'pass_att'), 0) != np.nansum(_col(S, 'targets'), 0) + thr, c, (n,))
        otd = _get(T, 'off_td')
        if otd is not None and _rep(S, 'rec_td', 'rush_td'):
            add('C05', otd != np.nansum(_col(S, 'rec_td'), 0) + np.nansum(_col(S, 'rush_td'), 0), c, (n,))
        pts = _get(T, 'points')
        K = cb.get('kicker') or {}
        dtd, std, sf = _get(T, 'def_td'), _get(T, 'st_td'), _get(T, 'safeties')
        xpm, tpm, fg = _get(K, 'xp_made'), _get(K, 'tp_made'), _get(K, 'fg_made')
        if pts is not None and otd is not None and xpm is not None and fg is not None:
            if dtd is not None and std is not None and tpm is not None and sf is not None:
                want = 6 * (otd + dtd + std) + xpm + 2 * tpm + 3 * fg + 2 * sf
                add('C06', np.abs(pts - want) > EQ_TOL, c, (n,))
            else:
                # The scoreboard does not itemise D/ST scoring or 2pt makes (the incumbent): read the D/ST TDs and
                # safeties this club's own DST block claims, and count the world as violated unless SOME feasible
                # number of successful 2pt tries (0 .. tp_att) reconciles the points exactly.
                tdx, sfx = _get(cb['dst'], 'dst_td'), _get(cb['dst'], 'safeties')
                tpa_ = _get(K, 'tp_att')
                if tdx is not None and sfx is not None and tpa_ is not None:
                    r = pts - (6 * (otd + tdx) + xpm + 3 * fg + 2 * sfx)
                    feasible = ((np.abs(r - 2 * np.round(r / 2)) <= EQ_TOL) & (r >= -EQ_TOL)
                                & (r <= 2 * tpa_ + EQ_TOL))
                    add('C06', ~feasible, c, (n,))
        if pts is not None:
            add('C07', (pts < -EQ_TOL) | (np.abs(pts - np.round(pts)) > 1e-9), c, (n,))
        xpa, tpa = _get(K, 'xp_att'), _get(K, 'tp_att')
        if xpa is not None and tpa is not None and xpm is not None and tpm is not None and otd is not None \
                and dtd is not None and std is not None:
            add('C08', (xpa + tpa != otd + dtd + std) | (xpm > xpa) | (tpm > tpa), c, (n,))
        bands = [_get(K, b) for b in FG_BAND_POINTS]
        if fg is not None and all(b is not None for b in bands):
            add('C09', fg != sum(bands), c, (n,))
            kdk = _get(K, 'dk')
            if kdk is not None and xpm is not None:
                add('C10', np.abs(kdk - (xpm + sum(FG_BAND_POINTS[b] * x for b, x in zip(FG_BAND_POINTS, bands))))
                    > EQ_TOL, c, (n,))
        npy, tsk, tsy = _get(T, 'net_pass_yards'), _get(T, 'sacks_taken'), _get(T, 'sack_yards')
        if npy is not None and tsk is not None and tsy is not None and _rep(S, 'pass_yards', 'sacks_taken', 'sack_yards'):
            add('C11', (np.abs(npy - (np.nansum(_col(S, 'pass_yards'), 0) - tsy)) > EQ_TOL)
                | (tsk != np.nansum(_col(S, 'sacks_taken'), 0)) | (np.abs(tsy - np.nansum(_col(S, 'sack_yards'), 0)) > EQ_TOL),
                c, (n,))
        tpa_, tra = _get(T, 'pass_att'), _get(T, 'rush_att')
        if tpa_ is not None and tra is not None and _rep(S, 'pass_att', 'carries'):
            add('C12', (tpa_ != np.nansum(_col(S, 'pass_att'), 0)) | (tra != np.nansum(_col(S, 'carries'), 0)), c, (n,))
        # ---------------------------------------------------------------- DST of c against the offence of o
        Dd = cb['dst']
        So = np.asarray(ob['S'], float)
        To = ob['team']
        d_int, d_sk, d_fr, d_ta = _get(Dd, 'ints'), _get(Dd, 'sacks'), _get(Dd, 'fum_rec'), _get(Dd, 'takeaways')
        if d_int is not None and _rep(So, 'ints'):
            add('D01', d_int != np.nansum(_col(So, 'ints'), 0), c, (n,))
        if d_ta is not None and _rep(So, 'ints'):
            add('D01W', np.nansum(_col(So, 'ints'), 0) > d_ta + 1e-9, c, (n,))
        if d_sk is not None and _rep(So, 'sacks_taken'):
            add('D02', d_sk != np.nansum(_col(So, 'sacks_taken'), 0), c, (n,))
        if d_fr is not None and _rep(So, 'fumbles_lost'):
            add('D03', d_fr != np.nansum(_col(So, 'fumbles_lost'), 0), c, (n,))
        if d_ta is not None and d_int is not None and d_fr is not None:
            add('D04', d_ta != d_int + d_fr, c, (n,))
        d_dtd, d_std, d_sf = _get(Dd, 'def_td'), _get(Dd, 'st_td'), _get(Dd, 'safeties')
        if d_dtd is not None and d_std is not None and dtd is not None and std is not None:
            add('D05', d_dtd + d_std != dtd + std, c, (n,))
        if d_sf is not None and sf is not None:
            add('D06', d_sf != sf, c, (n,))
        if d_dtd is not None and d_ta is not None:
            add('D07', d_dtd > d_ta, c, (n,))
        d_pa, d_tier, d_dk = _get(Dd, 'pa'), _get(Dd, 'tier'), _get(Dd, 'dk')
        opts, odtd, osf = _get(To, 'points'), _get(To, 'def_td'), _get(To, 'safeties')
        odc = _get(To, 'def_td_conv_points')
        if d_pa is not None and opts is not None and odtd is not None and osf is not None and odc is not None:
            add('D08', np.abs(d_pa - (opts - 6 * odtd - odc - 2 * osf)) > EQ_TOL, c, (n,))
        if d_tier is not None and d_pa is not None:
            add('D09', np.abs(d_tier - dk_tier(d_pa)) > EQ_TOL, c, (n,))
        if d_dk is not None and d_tier is not None and d_sk is not None and d_sf is not None:
            if d_int is not None and d_fr is not None and d_dtd is not None and d_std is not None:
                want = d_tier + d_sk + 2 * d_int + 2 * d_fr + 6 * (d_dtd + d_std) + 2 * d_sf
            else:
                tdx = _get(Dd, 'dst_td')
                want = None if (d_ta is None or tdx is None) else d_tier + d_sk + 2 * d_ta + 6 * tdx + 2 * d_sf
            if want is not None:
                add('D10', np.abs(d_dk - want) > EQ_TOL, c, (n,))
        # ---------------------------------------------------------------- scored
        dk = cb.get('dk')
        if dk:
            if dk.get('core') is not None:
                add('S01', np.abs(np.asarray(dk['core'], float) - dk_core(S)) > EQ_TOL, c, shp)
            # INT / fumble fields a provider does not draw enter as 0, exactly as its own DK formula treats them
            if dk.get('classic') is not None:
                add('S02', np.abs(np.asarray(dk['classic'], float) - dk_classic(S)) > EQ_TOL, c, shp)
        # ---------------------------------------------------------------- ledger
        L = (bundle.get('ledger') or {}).get(c)
        if L is not None:
            _check_ledger(L, S, pos, n, out)
    return out


KIND_PASS, KIND_SACK, KIND_RUSH = 0, 1, 2


def ledger_aggregate(L, n_players, n):
    """Player stat lines (P, n, PF) from an event ledger. The ONLY way an event-linked stat line is made."""
    S = np.zeros((n_players, n, len(PF)))
    w = np.asarray(L['world'], int)
    k = np.asarray(L['kind'], int)
    ps, rc, ru = (np.asarray(L[x], int) for x in ('passer', 'receiver', 'rusher'))
    cmp_, td, it, fl = (np.asarray(L[x], bool) for x in ('complete', 'td', 'int', 'fumble'))
    y = np.asarray(L['yards'], float)
    fb = np.asarray(L['fumbler'], int)

    def acc(mask, who, field, val):
        m = mask & (who >= 0)
        np.add.at(S, (who[m], w[m], PX[field]), val[m] if isinstance(val, np.ndarray) else val)
    pa = k == KIND_PASS
    acc(pa, ps, 'pass_att', 1.0)
    acc(pa & cmp_, ps, 'completions', 1.0)
    acc(pa & cmp_, ps, 'pass_yards', y)
    acc(pa & cmp_ & td, ps, 'pass_td', 1.0)
    acc(pa & it, ps, 'ints', 1.0)
    acc(pa & (rc >= 0), rc, 'targets', 1.0)
    acc(pa & cmp_, rc, 'receptions', 1.0)
    acc(pa & cmp_, rc, 'rec_yards', y)
    acc(pa & cmp_ & td, rc, 'rec_td', 1.0)
    sk = k == KIND_SACK
    acc(sk, ps, 'sacks_taken', 1.0)
    acc(sk, ps, 'sack_yards', -y)
    ru_ = k == KIND_RUSH
    acc(ru_, ru, 'carries', 1.0)
    acc(ru_, ru, 'rush_yards', y)
    acc(ru_ & td, ru, 'rush_td', 1.0)
    acc(fl, fb, 'fumbles_lost', 1.0)
    return S


def _check_ledger(L, S, pos, n, out):
    k = np.asarray(L['kind'], int)
    cmp_, td, it, fl = (np.asarray(L[x], bool) for x in ('complete', 'td', 'int', 'fumble'))
    y = np.asarray(L['yards'], float)
    ps, rc, ru, fb = (np.asarray(L[x], int) for x in ('passer', 'receiver', 'rusher', 'fumbler'))
    ne = len(k)

    def put(inv, v):
        r = out[inv]
        r['state'] = 'CHECKED'
        r['violations'] = (r['violations'] or 0) + int(np.asarray(v, bool).sum())
        r['units'] += ne
    put('E01', td & ~(((k == KIND_PASS) & cmp_) | (k == KIND_RUSH)))
    put('E02', it & ~((k == KIND_PASS) & ~cmp_))
    put('E03', (td.astype(int) + it.astype(int) + fl.astype(int)) > 1)
    put('E04', ((k == KIND_PASS) & ~cmp_ & (np.abs(y) > EQ_TOL)) | ((k == KIND_SACK) & (y > EQ_TOL))
        | ((k == KIND_PASS) & cmp_ & ~np.isfinite(y)))
    P_ = S.shape[0]
    agg = ledger_aggregate(L, P_, n)
    diff = np.abs(np.nan_to_num(S, nan=0.0) - agg) > EQ_TOL
    r = out['E05']
    r['state'] = 'CHECKED'
    r['violations'] = (r['violations'] or 0) + int(diff.any(axis=2).sum())
    r['units'] += P_ * n
    isqb = pos == 'QB'
    okp = (ps >= 0) & (ps < P_)
    bad = ((k == KIND_PASS) | (k == KIND_SACK)) & ~(okp & isqb[np.clip(ps, 0, P_ - 1)])
    bad |= (k == KIND_PASS) & (rc >= 0) & ((rc >= P_) | isqb[np.clip(rc, 0, P_ - 1)])
    bad |= (k == KIND_PASS) & cmp_ & (rc < 0)
    bad |= (k == KIND_RUSH) & ~((ru >= 0) & (ru < P_))
    bad |= fl & ~((fb >= 0) & (fb < P_))
    put('E06', bad)


def summarise(per_stage: dict) -> dict:
    """per_stage: {stage: [check_bundle results]} -> {stage: {inv: {state, violations, units}}} summed."""
    out = {}
    for st, results in per_stage.items():
        acc = {}
        for res in results:
            for inv, r in res.items():
                a = acc.setdefault(inv, {'state': 'NOT_REPRESENTED', 'violations': None, 'units': 0})
                if r['state'] == 'CHECKED':
                    a['state'] = 'CHECKED'
                    a['violations'] = (a['violations'] or 0) + r['violations']
                    a['units'] += r['units']
        out[st] = acc
    return out


def total_violations(stage_summary: dict) -> int:
    return int(sum(r['violations'] or 0 for r in stage_summary.values()))
