#!/usr/bin/env python3.12
"""GAP 10: defences, distributionally, driven by the same game the offence is drawn from.

WHY A DEFENCE IS THE EASIEST POSITION TO GET STRUCTURALLY RIGHT AND THE EASIEST TO FAKE

Most of a defence's DK score is a step function of one number the joint simulator already draws:
the points its opponent scores. The tier table is worth reading as the scoring rule it is --

    0 allowed 10 | 1-6  7 | 7-13  4 | 14-20  1 | 21-27  0 | 28-34  -1 | 35+  -4

-- because it means a defence is nearly a short position on the opposing offence, which is exactly
the correlation a point projection cannot express and a joint simulation gets for free. That is
the whole argument for doing it this way rather than projecting a defence's points directly.

The rest is sacks and takeaways. Those are measured, conditionally on the opponent's points,
because a defence that holds a club to six has usually also sacked it and taken the ball away, and
treating the three as independent would understate the good outcomes that matter most.

WHAT IS MISSING, AND THE DIRECTION IT BIASES

Defensive and return touchdowns are NOT in this warehouse and cannot be recovered from it: a
club's points decompose into offensive touchdowns, kicks, defensive scores and safeties, and only
the first is recorded. They are therefore EXCLUDED, not estimated, which makes every defensive
projection here a FLOOR and biases it downward. The omission is declared in the artifact, the bias
direction is stated, and OUT-041 asks for the data. It is not filled with a plausible number.
"""
from __future__ import annotations

import collections
import json
import math
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

TG = _REPO / 'nfl/warehouse/TEAM_GAME.json'
OUT = _REPO / 'nfl/sim/DST_MODEL.json'

POINTS_BANDS = ((0, 1, 10.0), (1, 7, 7.0), (7, 14, 4.0), (14, 21, 1.0), (21, 28, 0.0),
                (28, 35, -1.0), (35, 10 ** 6, -4.0))
SACK_POINTS = 1.0
TAKEAWAY_POINTS = 2.0
CONDITIONING_BANDS = ((0, 10), (10, 17), (17, 24), (24, 31), (31, 10 ** 6))
MIN_PER_BAND = 60


def tier(points_allowed: float) -> float:
    """DK's points-allowed tier. A step function, so it is written as one."""
    p = max(0.0, points_allowed)
    for lo, hi, v in POINTS_BANDS:
        if lo <= p < hi:
            return v
    return -4.0


def build() -> Outcome:
    if not TG.exists():
        return Outcome.blocked('DST_NO_TEAM_GAME', 'team-game table missing', cause=Cause.DATA)
    art = json.loads(TG.read_text())
    rows = art['rows'] if isinstance(art['rows'], list) else list(art['rows'].values())

    # a defence's sacks and takeaways are the OPPONENT's sacks taken and turnovers committed.
    # Verified against PLAYER_GAME: TEAM_GAME.sacks equals the club's own sacks_taken in 100% of
    # 2,782 comparable club-games, so reading it as a defensive stat would invert the model.
    by = {}
    for r in rows:
        by[(r['game_id'], r['club'])] = r
    obs = collections.defaultdict(list)
    n_used = 0
    for (gid, club), r in by.items():
        opp = r.get('opponent')
        o = by.get((gid, opp))
        if o is None:
            continue
        if not all(isinstance(o.get(k), (int, float)) for k in ('sacks', 'turnovers', 'points')):
            continue
        pa = float(o['points'])
        for lo, hi in CONDITIONING_BANDS:
            if lo <= pa < hi:
                obs[(lo, hi)].append((float(o['sacks']), float(o['turnovers'])))
                n_used += 1
                break
    thin = {f'{lo}-{hi}': len(v) for (lo, hi), v in obs.items() if len(v) < MIN_PER_BAND}
    if not obs or thin:
        return Outcome.blocked('DST_BANDS_TOO_THIN', 'a points-allowed band has too few games',
                               cause=Cause.DATA, thin_bands=thin, n_used=n_used)

    bands = {}
    for (lo, hi), v in sorted(obs.items()):
        sk = [a for a, _ in v]
        tk = [b for _, b in v]
        bands[f'{lo}-{hi}'] = {
            'n': len(v),
            'mean_sacks': round(sum(sk) / len(sk), 4),
            'mean_takeaways': round(sum(tk) / len(tk), 4),
            'empirical_pairs': [[a, b] for a, b in v],
        }
    # the relationship that makes this worth conditioning on at all
    allsk = [(pa, s, t) for (lo, hi), v in obs.items() for s, t in v
             for pa in [((lo + min(hi, 50)) / 2)]]
    n = len(allsk)
    mp = sum(a for a, _, _ in allsk) / n
    ms = sum(b for _, b, _ in allsk) / n
    mt = sum(c for _, _, c in allsk) / n
    def cor(xs, ys):
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        sxx = sum((x - mx) ** 2 for x in xs)
        syy = sum((y - my) ** 2 for y in ys)
        if sxx <= 0 or syy <= 0:
            return None
        return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(sxx * syy)
    out = {
        'ARTIFACT': 'DST_MODEL',
        'CONSTRUCTION': ('points allowed come from the joint simulation, so a defence is short the '
                         'opposing offence by construction. Sacks and takeaways are drawn from '
                         'the empirical pairs measured within the relevant points-allowed band, '
                         'which keeps their dependence on the game intact.'),
        'tier_table': [[lo, hi, v] for lo, hi, v in POINTS_BANDS],
        'sack_points': SACK_POINTS, 'takeaway_points': TAKEAWAY_POINTS,
        'bands': bands, 'n_club_games': n_used,
        'band_means_are_monotone_in_points_allowed': (
            [bands[k]['mean_sacks'] for k in bands] ==
            sorted([bands[k]['mean_sacks'] for k in bands], reverse=True)),
        'corr_band_points_with_sacks': None if cor([a for a, _, _ in allsk],
                                                   [b for _, b, _ in allsk]) is None
        else round(cor([a for a, _, _ in allsk], [b for _, b, _ in allsk]), 4),
        'corr_band_points_with_takeaways': None if cor([a for a, _, _ in allsk],
                                                       [c for _, _, c in allsk]) is None
        else round(cor([a for a, _, _ in allsk], [c for _, _, c in allsk]), 4),
        'EXCLUDED': {
            'component': 'defensive and return touchdowns',
            'state': 'NOT_AVAILABLE_FROM_THIS_WAREHOUSE',
            'why': ('a club\'s points decompose into offensive touchdowns, kicks, defensive '
                    'scores and safeties, and only offensive touchdowns are recorded. The others '
                    'are not separable from the total.'),
            'bias_direction': ('every defensive projection here is a FLOOR and is biased DOWNWARD. '
                               'Defensive scores are also the fattest part of a defence\'s upside, '
                               'so the understatement is worst exactly where a tournament cares.'),
            'data_request': 'OUT-041',
            'not_done': 'no plausible rate was substituted',
        },
    }
    OUT.write_text(json.dumps(out, indent=2))
    return Outcome.ok('DST_MODEL_MEASURED', value={
        k: v for k, v in out.items() if k != 'bands'} | {
        'band_summary': {k: {kk: vv for kk, vv in v.items() if kk != 'empirical_pairs'}
                         for k, v in bands.items()}})


class DstModel:
    def __init__(self, art: dict):
        self.bands = []
        for key, v in art['bands'].items():
            lo, hi = key.split('-')
            self.bands.append((float(lo), float(hi), v['empirical_pairs']))
        self.bands.sort()
        self.sack_pts = art['sack_points']
        self.take_pts = art['takeaway_points']

    @classmethod
    def load(cls) -> Outcome:
        if not OUT.exists():
            return Outcome.blocked('DST_MODEL_ABSENT', 'DST_MODEL.json missing', cause=Cause.DATA)
        return Outcome.ok('DST_MODEL_LOADED', value=cls(json.loads(OUT.read_text())))

    def draw(self, points_allowed: float, rng) -> float:
        """DK points for a defence, given what the simulated opponent scored."""
        pool = None
        for lo, hi, pairs in self.bands:
            if lo <= points_allowed < hi:
                pool = pairs
                break
        if pool is None:
            pool = self.bands[-1][2]
        sacks, takeaways = pool[rng.randrange(len(pool))]
        return (tier(points_allowed) + self.sack_pts * sacks + self.take_pts * takeaways)


if __name__ == '__main__':
    o = build()
    print(o.state.value, o.code)
    v = o.value if o.value else o.evidence
    if o.state.value == 'PASS':
        print(f"club-games {v['n_club_games']}")
        for k, b in v['band_summary'].items():
            print(f"  points allowed {k:8s} n={b['n']:5d}  mean sacks {b['mean_sacks']:.3f}  "
                  f"mean takeaways {b['mean_takeaways']:.3f}")
        print(f"  corr(points allowed, sacks) {v['corr_band_points_with_sacks']}, "
              f"takeaways {v['corr_band_points_with_takeaways']}")
        print(f"  EXCLUDED: {v['EXCLUDED']['component']} -> projections are a FLOOR")
    else:
        print(v)
    raise SystemExit(0 if o.state.value == 'PASS' else 1)
