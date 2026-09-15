"""Kicking from the same simulated worlds as the offense. Two models, not one.

THE SEPARATION THAT MATTERS, and it is the reason a single career FG% is wrong:

    OPPORTUNITY   how many field goals and extra points the GAME offers, which
                  is an offense/game-script quantity and has nothing to do with
                  who is kicking
    CONVERSION    whether THIS kicker makes THIS distance, which is a kicker
                  quantity and must be estimated per distance band

Collapsing them into one number per kicker prices a 26-yard attempt and a
54-yard attempt identically. Measured over 5,639 attempts, 2021 through 2026
week 1, strictly before ordinal 202602:

    FG<20   12/12      1.0000  (n=12, no kicker has enough for a kicker term)
    FG20s   1207/1231  0.9805
    FG30s   1473/1575  0.9352
    FG40s   1259/1577  0.7984
    FG50+   857/1244   0.6889
    XP      6180/6502  0.9505

OPPORTUNITY IS COUPLED TO GAME SCRIPT BY MEASUREMENT, NOT BY ASSERTION.
A drive that ends in a touchdown does not also produce a field goal, so field
goal attempts FALL as offensive touchdowns rise. Over 2,868 team-games:

    offensive TD   0     1     2     3     4     5     6
    mean FGA     2.237 2.282 2.108 1.839 1.631 1.360 0.967

So attempts are drawn conditional on the SAME DRAW's offensive touchdowns,
which come from the same simulated worlds the receivers and backs were scored
in. A high-scoring world gives its kicker extra points and few field goals; a
stalling world gives him the opposite. Nothing is reconciled afterwards.

NO PARAMETRIC FORM IS INVENTED. Attempts are resampled from the EMPIRICAL
conditional distribution of FGA (and XPA) given that touchdown count. The
conditional standard deviation is below the mean at every touchdown count, so a
Poisson would be visibly over-dispersed; rather than pick a two-parameter
family to patch that, the observed distribution is used directly.

THE KICKER TERM IS SHRUNK, AND THE STRENGTH IS ESTIMATED, NOT CHOSEN. Per
band, k = p(1-p)/between-kicker variance, with between = observed variance
minus the binomial component -- empirical Bayes over kickers with at least 20
attempts in that band. Measured k: 20s 204.9, 30s 196.1, 40s 93.2, 50+ 164.0.
The 40s band shrinks least because kickers genuinely differ most there.

FANTASYCRUNCHER IS SCHEMA AND VALIDATION EVIDENCE ONLY, NEVER AN INPUT.
Its historical rows are what established that the professional surface is
made/attempted BY DISTANCE BAND plus XP rather than a points total, which is
the shape emitted here. As a cross-check its Bates note says he was perfect
inside 40 and that five of seven misses came from 50+; this module's
independent extraction gives Bates 11/11 in the 20s, 18/18 in the 30s and
10/17 at 50+, which is seven misses. No FC projection is read, copied or
targeted -- one visible FC 2026 row carries Proj 0.00 against real production.
"""
from __future__ import annotations

import collections
import csv
import glob
import gzip
import hashlib
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome      # noqa: E402

SPEC_VERSION = 'kicking-opportunity-conversion-1'
BANDS = ((0, 20, 'FG<20'), (20, 30, 'FG20s'), (30, 40, 'FG30s'),
         (40, 50, 'FG40s'), (50, 99, 'FG50+'))
BAND_NAMES = tuple(b for _, _, b in BANDS)
MIN_FOR_EB = 20

#: DRAFTKINGS NFL KICKER SCORING, a published external rule rather than a
#: fitted quantity. Declared here so a reader can check it against DK's own
#: rules instead of finding it inline: FG under 40 = 3, 40-49 = 4, 50+ = 5,
#: extra point = 1. A scoring adapter is a CONVENTION, not a model parameter,
#: and changing platform must not change a single simulated event.
DK_FG_POINTS = {'FG<20': 3.0, 'FG20s': 3.0, 'FG30s': 3.0,
                'FG40s': 4.0, 'FG50+': 5.0}
DK_XP_POINTS = 1.0

_CACHE: dict = {}


def _band(d):
    for lo, hi, n in BANDS:
        if lo <= d < hi:
            return n
    return None


def _cut_ok(season, week, cut_ordinal):
    try:
        return int(season) * 100 + int(week) < cut_ordinal
    except (TypeError, ValueError):
        return False


def fit(cut_ordinal: int) -> Outcome:
    """Fit both models from play-by-play strictly before `cut_ordinal`."""
    key = ('fit', cut_ordinal)
    if key in _CACHE:
        return _CACHE[key]
    files = sorted(glob.glob(str(_REPO / 'nfl/research/postgame/pbp_20*.csv.gz')))
    if not files:
        return Outcome.blocked(
            'KICKING_PBP_ABSENT',
            'no play-by-play under nfl/research/postgame, so neither the '
            'distance bands nor the opportunity table can be fitted.',
            cause=Cause.DATA)

    lg = collections.Counter()
    per = collections.defaultdict(collections.Counter)
    tg = collections.defaultdict(lambda: {'td': 0, 'fga': 0, 'xpa': 0})
    xpa = xpm = 0
    mix = collections.Counter()
    for f in files:
        for r in csv.DictReader(gzip.open(f, 'rt')):
            if not _cut_ok(r.get('season'), r.get('week'), cut_ordinal):
                continue
            t, g = r.get('posteam'), r.get('game_id')
            if t and g:
                d = tg[(g, t)]
                if str(r.get('pass_touchdown') or '0') in ('1', '1.0'):
                    d['td'] += 1
                if str(r.get('rush_touchdown') or '0') in ('1', '1.0'):
                    d['td'] += 1
            fgr = (r.get('field_goal_result') or '').strip()
            if fgr in ('made', 'missed', 'blocked'):
                if t and g:
                    tg[(g, t)]['fga'] += 1
                try:
                    kd = float(r.get('kick_distance') or 0)
                except (TypeError, ValueError):
                    kd = 0.0
                b = _band(kd)
                if b:
                    made = 1 if fgr == 'made' else 0
                    lg[b + '_a'] += 1
                    lg[b + '_m'] += made
                    mix[b] += 1
                    k = (r.get('kicker_player_name') or '').strip()
                    if k:
                        per[k][b + '_a'] += 1
                        per[k][b + '_m'] += made
            xpr = (r.get('extra_point_result') or '').strip()
            if xpr in ('good', 'failed', 'blocked'):
                xpa += 1
                xpm += 1 if xpr == 'good' else 0
                if t and g:
                    tg[(g, t)]['xpa'] += 1

    if not lg or not tg:
        return Outcome.blocked(
            'KICKING_FIT_EMPTY',
            f'no kicking rows earlier than ordinal {cut_ordinal}. Zero rows '
            f'is an absence, not a league that kicks no field goals.',
            cause=Cause.DATA, cut_ordinal=cut_ordinal)

    # LEAGUE BAND RATES, JEFFREYS. FG<20 is 12/12; carrying 1.0000 would assert
    # a 19-yard kick cannot be missed, which 12 attempts cannot establish.
    band_p, band_n = {}, {}
    for b in BAND_NAMES:
        a, m = lg[b + '_a'], lg[b + '_m']
        band_n[b] = a
        band_p[b] = ((m + 0.5) / (a + 1.0)) if a else None

    # EMPIRICAL BAYES STRENGTH PER BAND.
    kstr = {}
    for b in BAND_NAMES:
        p = band_p[b]
        elig = [(per[k][b + '_m'], per[k][b + '_a']) for k in per
                if per[k][b + '_a'] >= MIN_FOR_EB]
        if p is None or len(elig) < 5:
            kstr[b] = None
            continue
        rates = [m / a for m, a in elig]
        mu = sum(rates) / len(rates)
        obs = sum((x - mu) ** 2 for x in rates) / len(rates)
        nbar = sum(a for _, a in elig) / len(elig)
        between = max(obs - p * (1 - p) / nbar, 1e-9)
        kstr[b] = p * (1 - p) / between

    # OPPORTUNITY: the empirical conditional distributions, not a fitted form.
    fga_by_td, xpa_by_td = collections.defaultdict(list), \
        collections.defaultdict(list)
    for d in tg.values():
        fga_by_td[min(d['td'], 6)].append(d['fga'])
        xpa_by_td[min(d['td'], 6)].append(d['xpa'])

    total_mix = sum(mix.values()) or 1
    doc = {
        'spec_version': SPEC_VERSION, 'cut_ordinal': cut_ordinal,
        'band_p': band_p, 'band_n': band_n, 'eb_strength': kstr,
        'xp_p': (xpm + 0.5) / (xpa + 1.0) if xpa else None,
        'xp_n': xpa,
        'distance_mix': {b: mix[b] / total_mix for b in BAND_NAMES},
        'fga_by_td': {k: v for k, v in fga_by_td.items()},
        'xpa_by_td': {k: v for k, v in xpa_by_td.items()},
        'kicker_counts': {k: dict(v) for k, v in per.items()},
        'n_team_games': len(tg), 'n_fg_attempts': sum(band_n.values()),
        'sources': [str(pathlib.Path(f).relative_to(_REPO)) for f in files],
    }
    out = Outcome.ok('KICKING_FIT_OK', value=doc, spec_version=SPEC_VERSION,
                     n_fg_attempts=doc['n_fg_attempts'],
                     n_team_games=len(tg), cut_ordinal=cut_ordinal)
    _CACHE[key] = out
    return out


def kicker_band_rates(doc, kicker_name):
    """Shrunk make probability per band for one kicker, with its basis."""
    rows = {}
    counts = (doc['kicker_counts'].get(kicker_name) or {})
    for b in BAND_NAMES:
        p = doc['band_p'][b]
        k = doc['eb_strength'][b]
        a = counts.get(b + '_a', 0)
        m = counts.get(b + '_m', 0)
        if p is None:
            rows[b] = {'p': None, 'basis': 'NO_LEAGUE_DATA', 'own': f'{m}/{a}'}
        elif k is None:
            rows[b] = {'p': p, 'basis': 'LEAGUE_ONLY_TOO_FEW_KICKERS_FOR_EB',
                       'own': f'{m}/{a}'}
        else:
            rows[b] = {'p': (m + k * p) / (a + k), 'basis': 'SHRUNK',
                       'own': f'{m}/{a}', 'k': k, 'league_p': p}
    return rows


def simulate(doc, kicker_name, team_td_draws, seed=20260908):
    """Kick the SAME worlds the offense was scored in.

    `team_td_draws` is that team's offensive touchdowns per draw, taken from
    the sealed player draws. Opportunity is conditioned on it draw by draw, so
    the coupling is structural rather than a correlation imposed afterwards.
    """
    rng = np.random.default_rng(seed)
    td = np.asarray(team_td_draws).astype(int)
    n = td.shape[0]
    rates = kicker_band_rates(doc, kicker_name)
    mix = np.array([doc['distance_mix'][b] for b in BAND_NAMES], dtype=float)
    mix = mix / mix.sum()
    xp_p = doc['xp_p']

    fga = np.zeros(n, dtype=int)
    xpa = np.zeros(n, dtype=int)
    for i in range(n):
        key = int(min(td[i], 6))
        pool = doc['fga_by_td'].get(key) or doc['fga_by_td'].get(
            min(doc['fga_by_td'], key=lambda z: abs(z - key)))
        fga[i] = pool[rng.integers(len(pool))]
        xpool = doc['xpa_by_td'].get(key) or [0]
        # XP OPPORTUNITY IS BOUNDED BY THE TOUCHDOWNS THIS DRAW ACTUALLY HAD.
        # The historical row is resampled for the two-point and defensive-score
        # texture, then clipped: a world with two offensive touchdowns cannot
        # offer four extra points.
        xpa[i] = min(int(xpool[rng.integers(len(xpool))]), int(td[i]))

    by_band_a = {b: np.zeros(n, dtype=int) for b in BAND_NAMES}
    by_band_m = {b: np.zeros(n, dtype=int) for b in BAND_NAMES}
    fgm = np.zeros(n, dtype=int)
    dk = np.zeros(n, dtype=float)
    for i in range(n):
        if fga[i] > 0:
            drawn = rng.multinomial(int(fga[i]), mix)
            for j, b in enumerate(BAND_NAMES):
                a = int(drawn[j])
                if not a:
                    continue
                by_band_a[b][i] = a
                p = rates[b]['p']
                mk = int(rng.binomial(a, p)) if p is not None else 0
                by_band_m[b][i] = mk
                fgm[i] += mk
                dk[i] += mk * DK_FG_POINTS[b]
        xm = int(rng.binomial(int(xpa[i]), xp_p)) if xpa[i] > 0 else 0
        dk[i] += xm * DK_XP_POINTS
        by_band_m['_xpm'] = by_band_m.get('_xpm')
    xpm = np.array([int(rng.binomial(int(x), xp_p)) if x > 0 else 0
                    for x in xpa])
    return {'fga': fga, 'fgm': fgm, 'xpa': xpa, 'xpm': xpm,
            'band_att': by_band_a, 'band_made': by_band_m, 'dk': dk,
            'rates': rates}
