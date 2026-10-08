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

THE TAIL, WHICH WAS THE HOLE AND IS NOW MEASURED

Defensive and return touchdowns were excluded as unrecoverable, because a club's points decompose
into offensive touchdowns, kicks, defensive scores and safeties and TEAM_GAME records only the
first. That was true of TEAM_GAME and false of the repository: play-by-play carries `td_team`,
`return_touchdown` and `safety`, so a score by the club that was NOT on offence is directly
countable. OUT-041 is closed from inside the checkout rather than by asking for data.

Measured over 2,782 club-games: 0.1197 defensive or return touchdowns per club-game, at least one in
11.2% of games, up to three; 0.0237 safeties. Worth 0.766 DK points on average -- which is how large
the floor was.

They condition on the same axis as everything else here, and in the direction football implies. A
defence allowing 0-10 points scores 0.188 touchdowns per game; one allowing 24 or more scores about
0.10. A dominant defence both holds the score down and takes it the other way, so the tail is
correlated with the tier rather than sprinkled on independently -- which is exactly what a tournament
distribution needs, because the good outcomes arrive together.
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
from nfl.warehouse import point_in_time as PIT  # noqa: E402

TG = PIT.resolve(_REPO / 'nfl/warehouse/TEAM_GAME.json')   # as of the cutoff in a sealed run
OUT = _REPO / 'nfl/sim/DST_MODEL.json'

POINTS_BANDS = ((0, 1, 10.0), (1, 7, 7.0), (7, 14, 4.0), (14, 21, 1.0), (21, 28, 0.0),
                (28, 35, -1.0), (35, 10 ** 6, -4.0))
SACK_POINTS = 1.0
TAKEAWAY_POINTS = 2.0
DEFENSIVE_TD_POINTS = 6.0
SAFETY_POINTS = 2.0
PBP_SEASONS = (2021, 2022, 2023, 2024, 2025, 2026)
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

    # defensive and return touchdowns, and safeties, straight from play-by-play. A score by the club
    # that was NOT on offence is a defensive or return touchdown, which is precisely what DK credits
    # to a defence. A muffed kick recovered in the end zone by the KICKING team is not counted here
    # and is a known, rare omission.
    import csv as _csv
    import gzip as _gzip
    from nfl.warehouse import sources
    pbp = collections.defaultdict(lambda: collections.Counter())
    seasons_read = []
    pbp_files = []
    for season in PBP_SEASONS:
        sel = sources.select(sources.registry()['play_by_play'], season=season)
        if sel.state.value != 'PASS':
            continue
        seasons_read.append(season)
        pbp_files.append(_REPO / sel.value['selected'])
        with _gzip.open(_REPO / sel.value['selected'], 'rt') as fh:
            for row in _csv.DictReader(fh):
                if row.get('season_type') != 'REG':
                    continue
                gid, dft, tdt = row.get('game_id'), row.get('defteam'), row.get('td_team')
                if not gid or not dft:
                    continue
                if row.get('touchdown') == '1' and tdt and tdt == dft:
                    pbp[(gid, dft)]['def_td'] += 1
                    if row.get('return_touchdown') == '1':
                        pbp[(gid, dft)]['return_td'] += 1
                if row.get('safety') == '1':
                    pbp[(gid, dft)]['safety'] += 1
    if not seasons_read:
        return Outcome.blocked('DST_NO_PLAY_BY_PLAY',
                               'no play-by-play season could be selected, so the scoring tail '
                               'cannot be measured', cause=Cause.DATA)

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
        ev = pbp.get((gid, club), {})
        for lo, hi in CONDITIONING_BANDS:
            if lo <= pa < hi:
                # the whole four-tuple is kept together, so a shutout that also produced a pick-six
                # is drawn as one outcome rather than assembled from independent parts
                obs[(lo, hi)].append((float(o['sacks']), float(o['turnovers']),
                                      float(ev.get('def_td', 0)), float(ev.get('safety', 0))))
                n_used += 1
                break
    thin = {f'{lo}-{hi}': len(v) for (lo, hi), v in obs.items() if len(v) < MIN_PER_BAND}
    if not obs or thin:
        return Outcome.blocked('DST_BANDS_TOO_THIN', 'a points-allowed band has too few games',
                               cause=Cause.DATA, thin_bands=thin, n_used=n_used)

    bands = {}
    for (lo, hi), v in sorted(obs.items()):
        sk = [t[0] for t in v]
        tk = [t[1] for t in v]
        dt = [t[2] for t in v]
        sf = [t[3] for t in v]
        bands[f'{lo}-{hi}'] = {
            'n': len(v),
            'mean_sacks': round(sum(sk) / len(sk), 4),
            'mean_takeaways': round(sum(tk) / len(tk), 4),
            'mean_defensive_td': round(sum(dt) / len(dt), 4),
            'mean_safety': round(sum(sf) / len(sf), 4),
            'share_with_a_defensive_td': round(sum(1 for x in dt if x) / len(dt), 4),
            'empirical_tuples': [[a, b, c, d] for a, b, c, d in v],
        }
    # the relationship that makes this worth conditioning on at all
    allsk = [(pa, t[0], t[1]) for (lo, hi), v in obs.items() for t in v
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
        'defensive_td_points': DEFENSIVE_TD_POINTS, 'safety_points': SAFETY_POINTS,
        'scoring_tail': {
            'state': 'MEASURED_FROM_PLAY_BY_PLAY',
            'seasons_read': seasons_read,
            'closes': 'OUT-041',
            'definition': ('a touchdown whose scoring club was NOT the club on offence, which is '
                           'what DK credits to a defence, plus safeties'),
            'known_omission': ('a muffed kick recovered in the end zone by the KICKING team is not '
                               'counted; it is rare and it is named rather than absorbed'),
            'WAS_PREVIOUSLY': ('excluded as unrecoverable, because TEAM_GAME records only '
                               'offensive touchdowns. That was true of TEAM_GAME and false of the '
                               'repository: play-by-play carries td_team and safety directly.'),
        },
    }
    OUT.write_text(json.dumps(out, indent=2))
    # a derived artifact records what it was built FROM, not merely when -- readiness compares
    # lineage, not timestamps, so a DST model rebuilt from an older play-by-play pull or by older
    # code has to be visible as STALE_DEPENDENCY rather than as a fresh file.
    from nfl.production import lineage
    st = lineage.stamp(OUT, inputs=[TG] + pbp_files, code=[pathlib.Path(__file__)])
    if st.state.value != 'PASS':
        return st
    return Outcome.ok('DST_MODEL_MEASURED', value={
        k: v for k, v in out.items() if k != 'bands'} | {
        'band_summary': {k: {kk: vv for kk, vv in v.items() if kk != 'empirical_tuples'}
                         for k, v in bands.items()}})


class DstModel:
    def __init__(self, art: dict):
        self.bands = []
        for key, v in art['bands'].items():
            lo, hi = key.split('-')
            self.bands.append((float(lo), float(hi), v['empirical_tuples']))
        self.bands.sort()
        self.sack_pts = art['sack_points']
        self.take_pts = art['takeaway_points']
        self.td_pts = art.get('defensive_td_points', DEFENSIVE_TD_POINTS)
        self.safety_pts = art.get('safety_points', SAFETY_POINTS)

    @classmethod
    def load(cls) -> Outcome:
        if not OUT.exists():
            return Outcome.blocked('DST_MODEL_ABSENT', 'DST_MODEL.json missing', cause=Cause.DATA)
        return Outcome.ok('DST_MODEL_LOADED', value=cls(json.loads(OUT.read_text())))

    def draw(self, points_allowed: float, rng) -> float:
        """DK points for a defence, given what the simulated opponent scored."""
        return self.draw_components(points_allowed, rng)[0]

    def draw_components(self, points_allowed: float, rng):
        """(DK points, sacks, takeaways, defensive TDs, safeties). Same single rng draw as `draw`,
        so retaining the components changes no world."""
        pool = None
        for lo, hi, pairs in self.bands:
            if lo <= points_allowed < hi:
                pool = pairs
                break
        if pool is None:
            pool = self.bands[-1][2]
        sacks, takeaways, def_td, safety = pool[rng.randrange(len(pool))]
        return ((tier(points_allowed) + self.sack_pts * sacks + self.take_pts * takeaways
                 + self.td_pts * def_td + self.safety_pts * safety), sacks, takeaways, def_td, safety)


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
        t = v['scoring_tail']
        print(f"  scoring tail {t['state']} over seasons {t['seasons_read']} -> {t['closes']} closed")
        for k, b in v['band_summary'].items():
            print(f"    {k:8s} defensive/return TD {b['mean_defensive_td']:.4f}/game "
                  f"(>=1 in {b['share_with_a_defensive_td']:.1%}), safety {b['mean_safety']:.4f}")
    else:
        print(v)
    raise SystemExit(0 if o.state.value == 'PASS' else 1)
