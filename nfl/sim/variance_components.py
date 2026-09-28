#!/usr/bin/env python3.12
"""GAP 3 repair, measured: how much of a player's day is his club's, and how much is his own.

WHAT THIS REPLACES

The simulator split a club's yards over its players with a Dirichlet concentration of 12.0. That
number was invented. It controls exactly one thing -- how far a player's share of the club's
yards drifts from his share of the club's opportunities -- and that quantity is measurable, so
carrying it as a constant was carrying a fitted coefficient without fitting it.

It is also the number that produced the defect the validation named. Too high a concentration
pins every player to the club's day and over-couples same-club pairs; the measured misses were
exactly that, mean gap +0.065 on same-club pairs without the quarterback and +0.091 on pairs with
the lead back.

THE DERIVATION

For a Dirichlet with concentration a over opportunity shares w, the realised yards share s has

    E[s_i] = w_i          Var(s_i) = w_i (1 - w_i) / (a + 1)

so a is identified by the observed dispersion of s about w:

    a = w (1 - w) / Var(s - w) - 1

Both sides are measurable from PLAYER_GAME at club-game level, which makes this an estimate with
a standard error rather than a setting. It is estimated separately for receiving and rushing,
because there is no reason they should agree and the validation suggests they do not.
"""
from __future__ import annotations

import collections
import json
import math
import pathlib
import random
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

PG = _REPO / 'nfl/warehouse/PLAYER_GAME.json'
OUT = _REPO / 'nfl/sim/VARIANCE_COMPONENTS.json'
MIN_OPP = 3
MIN_CLUB_OPP = 15
MIN_OBS = 300
BOOT = 400


def _estimate(pairs, seed=41):
    """pairs: (w, s) per player-club-game. Returns the concentration implied by the dispersion."""
    n = len(pairs)
    if n < MIN_OBS:
        return {'state': 'NOT_IDENTIFIED_TOO_FEW', 'n': n}

    def conc(sample):
        num = sum(w * (1 - w) for w, _ in sample) / len(sample)
        var = sum((s - w) ** 2 for w, s in sample) / len(sample)
        if var <= 0:
            return None
        return num / var - 1.0

    point = conc(pairs)
    if point is None or point <= 0:
        return {'state': 'NOT_IDENTIFIED_NONPOSITIVE', 'n': n, 'raw': point}
    rng = random.Random(seed)
    boots = []
    for _ in range(BOOT):
        s = [pairs[rng.randrange(n)] for _ in range(n)]
        c = conc(s)
        if c is not None and c > 0:
            boots.append(c)
    boots.sort()
    mean_w = sum(w for w, _ in pairs) / n
    return {
        'state': 'ESTIMATED', 'concentration': round(point, 4), 'n_observations': n,
        'ci95': [round(boots[int(0.025 * len(boots))], 4),
                 round(boots[int(0.975 * len(boots))], 4)] if len(boots) > 40 else None,
        'mean_opportunity_share': round(mean_w, 4),
        'mean_abs_share_drift': round(sum(abs(s - w) for w, s in pairs) / n, 4),
        'DERIVATION': 'a = mean[w(1-w)] / mean[(s-w)^2] - 1, from the Dirichlet share variance',
    }


def share_dispersion(club, field, min_club=15, min_games=6, min_share=0.05, seed=47):
    """How much more a player's share of club opportunity varies than multinomial sampling allows.

    THE CHANNEL THAT ACTUALLY EXPLAINED THE DEFECT. Allocating club volume by a plain multinomial
    over PREGAME shares admits only sampling noise. Real shares move far more than that, and by
    very different amounts by position: targets came in at 1.21x the multinomial variance and
    carries at 2.78x. Backfield splits are volatile in a way receiver rotations are not, which is
    exactly the pattern of the correlation misses -- every pair involving the lead back missed,
    receiver pairs were close.

    A Dirichlet-multinomial with concentration a has variance n*w*(1-w)*(a+n)/(a+1), so the
    measured ratio identifies a directly:

        a = (n_bar - ratio) / (ratio - 1)

    which makes the concentration a measurement with an interval, not a smoothing choice.
    """
    import collections
    obs = collections.defaultdict(list)
    for players in club.values():
        ct = sum(float(p[field]) for p in players if isinstance(p.get(field), (int, float)))
        if ct < min_club:
            continue
        for p in players:
            t = p.get(field)
            if isinstance(t, (int, float)):
                obs[(p['player_id'], p['season'])].append((t / ct, ct))
    per = []
    for v in obs.values():
        if len(v) < min_games:
            continue
        sh = [x for x, _ in v]
        m = sum(sh) / len(sh)
        if m <= min_share:
            continue
        var_obs = sum((x - m) ** 2 for x in sh) / (len(sh) - 1)
        var_exp = sum(m * (1 - m) / ct for _, ct in v) / len(v)
        per.append((var_obs, var_exp, sum(ct for _, ct in v) / len(v)))
    if len(per) < 100:
        return {'state': 'NOT_IDENTIFIED_TOO_FEW_PLAYER_SEASONS', 'n': len(per)}
    ratio = sum(a for a, _, _ in per) / sum(b for _, b, _ in per)
    nbar = sum(c for _, _, c in per) / len(per)
    rng = random.Random(seed)
    boots = []
    for _ in range(BOOT):
        smp = [per[rng.randrange(len(per))] for _ in range(len(per))]
        r = sum(a for a, _, _ in smp) / sum(b for _, b, _ in smp)
        if r > 1.0001:
            boots.append((nbar - r) / (r - 1))
    boots.sort()
    if ratio <= 1.0001:
        return {'state': 'NO_OVERDISPERSION_DETECTED', 'ratio': round(ratio, 4),
                'n_player_seasons': len(per),
                'meaning': 'a plain multinomial is adequate for this field'}
    alpha = (nbar - ratio) / (ratio - 1)
    return {
        'state': 'ESTIMATED', 'overdispersion_ratio': round(ratio, 4),
        'mean_club_opportunities': round(nbar, 3),
        'concentration': round(alpha, 3),
        'ci95': ([round(boots[int(0.025 * len(boots))], 2),
                  round(boots[int(0.975 * len(boots))], 2)] if len(boots) > 40 else None),
        'n_player_seasons': len(per),
        'DERIVATION': 'a = (n_bar - ratio) / (ratio - 1), from the Dirichlet-multinomial variance',
        'READING': ('a LOWER concentration means a more volatile split. Carries come out far '
                    'more volatile than targets, which is what a backfield actually is.'),
    }


def build() -> Outcome:
    if not PG.exists():
        return Outcome.blocked('VC_NO_PLAYER_GAME', 'player-game table missing', cause=Cause.DATA)
    art = json.loads(PG.read_text())
    rows = art['rows'] if isinstance(art['rows'], list) else list(art['rows'].values())

    club = collections.defaultdict(list)
    for r in rows:
        club[(r['game_id'], r['club'])].append(r)

    rec_pairs, rush_pairs = [], []
    for players in club.values():
        ct = sum(float(p['targets']) for p in players if isinstance(p.get('targets'), (int, float)))
        cy = sum(float(p['receiving_yards']) for p in players
                 if isinstance(p.get('receiving_yards'), (int, float)))
        cc = sum(float(p['carries']) for p in players if isinstance(p.get('carries'), (int, float)))
        cry = sum(float(p['rushing_yards']) for p in players
                  if isinstance(p.get('rushing_yards'), (int, float)))
        if ct >= MIN_CLUB_OPP and cy > 0:
            for p in players:
                t = p.get('targets')
                y = p.get('receiving_yards')
                if isinstance(t, (int, float)) and isinstance(y, (int, float)) and t >= MIN_OPP:
                    rec_pairs.append((t / ct, y / cy))
        if cc >= MIN_CLUB_OPP and cry > 0:
            for p in players:
                c = p.get('carries')
                y = p.get('rushing_yards')
                if isinstance(c, (int, float)) and isinstance(y, (int, float)) and c >= MIN_OPP:
                    rush_pairs.append((c / cc, y / cry))

    receiving = _estimate(rec_pairs)
    rushing = _estimate(rush_pairs, seed=43)
    disp_targets = share_dispersion(club, 'targets')
    disp_carries = share_dispersion(club, 'carries')
    out = {
        'ARTIFACT': 'VARIANCE_COMPONENTS',
        'REPLACES': 'the invented Dirichlet concentration of 12.0 in nfl/sim/game.py',
        'WHY': ('the concentration controls how far a player\'s share of club yards drifts from '
                'his share of club opportunities. That is measurable, so carrying it as a '
                'constant was carrying an unfitted coefficient -- and it is the coefficient the '
                'correlation validation identified as the defect.'),
        'receiving': receiving, 'rushing': rushing,
        'share_dispersion_targets': disp_targets,
        'share_dispersion_carries': disp_carries,
        'SHARE_DISPERSION_IS_THE_ONE_THAT_MATTERED': (
            'three hypotheses for the correlation over-coupling were tested and refuted -- the '
            'yards-share concentration (measured HIGHER than the guess, so correcting it made the '
            'symptom slightly worse), target-share overdispersion at only 1.21x, and touchdown '
            'determinism (points explain touchdowns at r=+0.89, so the simulator was already '
            'slightly more random than reality). Carry-share dispersion at 2.78x is the channel '
            'that matches the pattern of the misses.'),
        'filters': {'min_player_opportunities': MIN_OPP, 'min_club_opportunities': MIN_CLUB_OPP},
        'INTERPRETATION': ('a LOWER concentration means more player-level idiosyncrasy and '
                           'therefore weaker same-club correlation. The previous 12.0 was a '
                           'guess about exactly this.'),
    }
    OUT.write_text(json.dumps(out, indent=2))
    if receiving.get('state') != 'ESTIMATED' or rushing.get('state') != 'ESTIMATED':
        return Outcome.fail('VC_NOT_IDENTIFIED', 'one or both components could not be estimated',
                            receiving=receiving, rushing=rushing)
    return Outcome.ok('VARIANCE_COMPONENTS_ESTIMATED', value=out)


if __name__ == '__main__':
    o = build()
    print(o.state.value, o.code)
    v = o.value if o.value else o.evidence
    for k in ('share_dispersion_targets', 'share_dispersion_carries'):
        d = v.get(k, {})
        if d.get('state') == 'ESTIMATED':
            print(f"  {k:28s} ratio {d['overdispersion_ratio']}x -> concentration "
                  f"{d['concentration']} ci{d['ci95']} (n_bar {d['mean_club_opportunities']})")
        else:
            print(f"  {k:28s} {d.get('state')}")
    for k in ('receiving', 'rushing'):
        d = v[k]
        if d.get('state') == 'ESTIMATED':
            print(f"  {k:10s} concentration {d['concentration']} ci{d['ci95']}  "
                  f"n={d['n_observations']}  mean share {d['mean_opportunity_share']}  "
                  f"mean drift {d['mean_abs_share_drift']}")
        else:
            print(f"  {k:10s} {d}")
    print('  previous invented value: 12.0')
    raise SystemExit(0 if o.state.value == 'PASS' else 1)
