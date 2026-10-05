#!/usr/bin/env python3.12
"""The kicker is scored inside the simulated world: identities hold and his score moves with his offence."""
import pathlib
import random
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))

from nfl.tools import kicker_world as KW  # noqa: E402

P = F = 0


def check(ok, what):
    global P, F
    P, F = P + bool(ok), F + (not ok)
    print(f"  {'ok  ' if ok else 'FAIL'} {what}")


MIX = {'made_mix': {'fg_0_39': 0.55, 'fg_40_49': 0.27, 'fg_50_plus': 0.18},
       'make_rate': {'fg_0_39': 0.95, 'fg_40_49': 0.8, 'fg_50_plus': 0.65}}


def test_rates_are_measured_not_typed():
    r = KW.load()['rates']
    check(r['n_club_games'] > 2000, f"rates come from {r['n_club_games']} club-games of play-by-play")
    check(0.9 < r['pat_make_rate'] < 0.99 and r['pat_make_rate'] != 0.96,
          f"PAT rate is the measured {r['pat_make_rate']}, not the old typed 0.96")
    check(0.5 < r['fg_share'] < 1.0, f"field goals are {r['fg_share']:.1%} of points not from offensive TDs")


def test_identities_per_world():
    r = KW.load()['rates']
    rng = random.Random(1)
    bad = 0
    for _ in range(5000):
        td = rng.randint(0, 6)
        pts = max(0.0, td * 6.3 + rng.gauss(6, 4))
        dk, d = KW.draw(pts, td, MIX, r, rng)
        made = sum(d[f'{b}_made'] for b in KW.BANDS())
        bad += (d['xp_att'] > td or d['xp_made'] > d['xp_att'] or made != d['fg_made']
                or d['fg_att'] < d['fg_made'] or dk != d['xp_made'] + sum(
                    KW.BAND_POINTS[b] * d[f'{b}_made'] for b in KW.BANDS()))
    check(bad == 0, f'XP <= TDs, makes <= attempts, DK = XP + band points in every world ({bad} violations)')
    dk, d = KW.draw(0.0, 0, MIX, r, rng)
    check(dk == 0 and d['fg_made'] == 0, 'a shut-out world scores the kicker zero')


def test_kicker_moves_with_his_offence():
    r = KW.load()['rates']
    rng = random.Random(2)
    lo = [KW.draw(10.0, 1, MIX, r, rng)[0] for _ in range(4000)]
    hi = [KW.draw(34.0, 4, MIX, r, rng)[0] for _ in range(4000)]
    check(sum(hi) / 4000 > sum(lo) / 4000 + 2,
          f'34-point world {sum(hi) / 4000:.2f} vs 10-point world {sum(lo) / 4000:.2f}')


for t in (test_rates_are_measured_not_typed, test_identities_per_world, test_kicker_moves_with_his_offence):
    print('##', t.__name__)
    t()
print(f'\nPASSED {P} FAILED {F}')
sys.exit(1 if F else 0)
