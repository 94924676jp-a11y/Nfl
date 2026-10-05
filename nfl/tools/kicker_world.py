"""Kicker scoring drawn INSIDE each simulated football world, not beside it.

WHY. `showdown_draws.kicker_draws` drew a kicker's attempts from Poisson rates that never saw the
world: a world in which his club scored 6 points and one in which it scored 41 produced the same
kicker distribution, so kicker/offence correlation was zero by construction and a kicker captain
could not be evaluated against a game script. Its PAT make rate was also a hard-coded 0.96 while
`kicker_model.measure()` already measured the league rate. Owner directive 2026-10-05: K and DST
are simulated in the SAME world as the offence.

WHAT A WORLD ALREADY FIXES. `nfl/sim/game.py` draws club points and inverts them into an offensive
touchdown count (SHARED_STATE scoring block). Given those two numbers per world, the kicker follows
from identities plus four MEASURED rates, each read from 2021-2025 regular-season play-by-play by
`measure()` below. Nothing here is chosen or fitted to a target:

  try_rate_2pt     two-point tries per offensive touchdown               (measured)
  pat_make_rate    extra points good / attempted                         (measured)
  fg_share         field-goal points / points NOT from offensive TDs     (measured; the rest is
                   safeties, defensive and return scores)
  band mix         each club's own made-FG distance mix, from kicker_model's per-club attempt rates
                   times the league make rate by band (measured), for DK's 3/4/5 distance scoring

  XP attempts   ~ Binomial(offensive TDs, 1 - try_rate_2pt)
  XP made       ~ Binomial(XP attempts, pat_make_rate)
  remainder     = club points - 6*TD - XP made - 2*(2pt tries x measured 2pt success)   (identity)
  FG made       = round(fg_share * remainder / 3), floored at 0
  FG band       ~ Categorical(club's made-band mix), per made kick
  FG misses     ~ NegativeBinomial(made in band, band make rate)  -- reported, not scored
                  (DK Showdown awards no points for, and deducts none for, a miss; see MISS_RULE)

DECLARED LIMITS, NOT HIDDEN: blocked kicks are inside the measured rates; weather is not modelled
(tonight is a dome); a kicker change mid-season is not modelled; non-offensive touchdowns'
extra points are not credited (they sit in the remainder, which fg_share discounts).
"""
from __future__ import annotations

import collections
import csv
import gzip
import json
import math
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import kicker_model  # noqa: E402

SPEC_VERSION = 'kicker-world-1'
OUT = _REPO / 'nfl/derived/KICKER_WORLD.json'
SEASONS = (2021, 2022, 2023, 2024, 2025)
BAND_POINTS = {'fg_0_39': 3.0, 'fg_40_49': 4.0, 'fg_50_plus': 5.0}
MISS_RULE = ('DraftKings NFL Showdown kicker scoring lists FG 0-39 +3, 40-49 +4, 50+ +5 and XP +1 '
             'with no deduction for a miss; misses are drawn for the decomposition only. '
             'kicker_model.project carries fg_miss -1 in its POINT projection: that disagreement '
             'is recorded, not resolved here, and these draws do not use it.')


def _pbp_paths():
    d = _REPO / 'nfl/research/postgame'
    out = {}
    for s in SEASONS:
        c = sorted(d.glob(f'pbp_{s}.*.csv.gz'))
        if len(c) != 1:
            raise RuntimeError(f'KICKER_WORLD_PBP_AMBIGUOUS season {s}: {[p.name for p in c]}')
        out[s] = c[0]
    return out


def measure():
    g = collections.defaultdict(collections.Counter)    # (game_id, club) -> counts
    final = {}
    for s, path in _pbp_paths().items():
        with gzip.open(path, 'rt', newline='', encoding='utf-8') as fh:
            for r in csv.DictReader(fh):
                if r.get('season_type') != 'REG':
                    continue
                gid = r['game_id']
                if r.get('home_score') and r.get('away_score'):
                    final[gid] = {r['home_team']: int(float(r['home_score'])),
                                  r['away_team']: int(float(r['away_score']))}
                pos = r.get('posteam')
                if not pos:
                    continue
                k = (gid, pos)
                if (r.get('td_team') == pos and (r.get('pass_touchdown') == '1'
                                                 or r.get('rush_touchdown') == '1')):
                    g[k]['off_td'] += 1
                if r.get('extra_point_attempt') == '1':
                    g[k]['xp_att'] += 1
                    g[k]['xp_made'] += r.get('extra_point_result') == 'good'
                if r.get('two_point_attempt') == '1':
                    g[k]['tp_att'] += 1
                    g[k]['tp_made'] += r.get('two_point_conv_result') == 'success'
                if r.get('field_goal_attempt') == '1' and r.get('field_goal_result') == 'made':
                    g[k]['fg_made'] += 1
    tot = collections.Counter()
    n = 0
    for (gid, club), c in g.items():
        pts = (final.get(gid) or {}).get(club)
        if pts is None:
            continue
        n += 1
        tot.update(c)
        tot['points'] += pts
    if n < 1000 or tot['off_td'] == 0 or tot['xp_att'] == 0:
        raise RuntimeError(f'KICKER_WORLD_MEASUREMENT_EMPTY: n={n} {dict(tot)}')
    non_td = tot['points'] - 6 * tot['off_td'] - tot['xp_made'] - 2 * tot['tp_made']
    m = {
        'n_club_games': n, 'seasons': list(SEASONS), 'counts': dict(tot),
        'try_rate_2pt': round(tot['tp_att'] / tot['off_td'], 5),
        'two_pt_success': round(tot['tp_made'] / tot['tp_att'], 5) if tot['tp_att'] else 0.0,
        'pat_make_rate': round(tot['xp_made'] / tot['xp_att'], 5),
        'fg_share': round(3 * tot['fg_made'] / non_td, 5),
        'points_not_from_off_td_per_game': round(non_td / n, 4),
        'xp_per_off_td': round(tot['xp_att'] / tot['off_td'], 5),
    }
    return m


def write():
    m = measure()
    art = {'ARTIFACT': 'KICKER_WORLD', 'spec_version': SPEC_VERSION,
           'source': {s: str(p.relative_to(_REPO)) for s, p in _pbp_paths().items()},
           'rates': m, 'MISS_RULE': MISS_RULE}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(art, indent=1, sort_keys=True) + '\n')
    return art


def load():
    if not OUT.exists():
        return write()
    return json.loads(OUT.read_text())


_KM = {}


def band_mix(club):
    """The club's made-FG distance mix and band make rates, from kicker_model's measurements."""
    if 'm' not in _KM:
        km = kicker_model.measure()
        _KM['m'] = km.value if hasattr(km, 'value') else km
    km = _KM['m']
    proj = kicker_model.project(club, km)
    if proj.get('dk_points') is None:
        return None
    w, mr = {}, {}
    for b in BANDS():
        it = proj['items'].get(b) or {}
        mr[b] = float(it.get('make_rate') or 0.0)
        w[b] = float(it.get('attempts') or 0.0) * mr[b]
    s = sum(w.values())
    if s <= 0:
        return None
    return {'made_mix': {b: v / s for b, v in w.items()}, 'make_rate': mr}


def club_kicker(club, candidates):
    """Which of a club's DK kicker rows actually kicks: the gsis_id with the most recent FG/XP attempt for
    the club in the latest 2026 play-by-play capture. Measured, never the row order. Returns
    (gsis_id or None, evidence)."""
    caps = sorted((_REPO / 'nfl/research/postgame').glob('pbp_2026.*.csv.gz'), key=lambda p: p.stat().st_mtime)
    if not caps:
        return None, 'NO_2026_PBP_CAPTURE'
    last = {}
    with gzip.open(caps[-1], 'rt', newline='', encoding='utf-8') as fh:
        for r in csv.DictReader(fh):
            if r.get('posteam') != club or not r.get('kicker_player_id'):
                continue
            if r.get('field_goal_attempt') == '1' or r.get('extra_point_attempt') == '1':
                key = (int(r['week']), int(r.get('play_id') or 0))
                kid = r['kicker_player_id']
                if kid not in last or key > last[kid]:
                    last[kid] = key
    cand = [g for g in candidates if g in last]
    if not cand:
        return None, f'none of {candidates} kicked for {club} in {caps[-1].name}'
    best = max(cand, key=lambda g: last[g])
    return best, f'{best} last kicked for {club} in week {last[best][0]} ({caps[-1].name})'


def BANDS():
    return tuple(BAND_POINTS)


def _binom(n, p, rng):
    return sum(1 for _ in range(int(n)) if rng.random() < p)


def _negbin_failures(k, p, rng):
    """Failures before k successes at success rate p (attempts are independent Bernoulli)."""
    if k <= 0 or p >= 1.0:
        return 0
    f = 0
    for _ in range(k):
        while rng.random() >= p:
            f += 1
    return f


def draw(points, off_td, mix, rates, rng):
    """One world's kicker line for one club. Returns (dk_points, detail dict)."""
    td = int(off_td)
    tp_att = _binom(td, rates['try_rate_2pt'], rng)
    tp_made = _binom(tp_att, rates['two_pt_success'], rng)
    xp_att = td - tp_att
    xp_made = _binom(xp_att, rates['pat_make_rate'], rng)
    remainder = points - 6 * td - xp_made - 2 * tp_made
    fg_made = max(0, int(round(rates['fg_share'] * remainder / 3.0)))
    bands = list(mix['made_mix'])
    cum, acc = [], 0.0
    for b in bands:
        acc += mix['made_mix'][b]
        cum.append(acc)
    made = collections.Counter()
    for _ in range(fg_made):
        u = rng.random() * acc
        made[next(b for b, c in zip(bands, cum) if u <= c)] += 1
    miss = {b: _negbin_failures(made[b], mix['make_rate'][b], rng) for b in bands}
    dk = xp_made + sum(BAND_POINTS[b] * made[b] for b in bands)
    return dk, {'xp_att': xp_att, 'xp_made': xp_made, 'fg_made': fg_made,
                'fg_att': fg_made + sum(miss.values()),
                **{f'{b}_made': made[b] for b in bands},
                'remainder_negative': remainder < 0}


if __name__ == '__main__':
    print(json.dumps(write()['rates'], indent=1))
