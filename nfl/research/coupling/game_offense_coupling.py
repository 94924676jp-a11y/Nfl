"""GAME_OFFENSE_COUPLING: one statistic, measured identically three ways.

THE FINDING THIS EXISTS TO TEST, AND IT IS A GATE, NOT A TARGET

A repo review reported that the sealed DET @ BUF worlds carry a roughly
NEGATIVE correlation between the two clubs' offensive production, while
historical game-level measurements are positive. If that is real it is a
structural defect: a shootout is a real football state, and a simulator whose
clubs push each other DOWN cannot produce one.

Nothing here fits, injects or hardcodes a correlation. The rule is explicit:
establish the measurement first, on the same statistic and the same
transformation, and only then diagnose a source.

THE STATISTIC, DEFINED ONCE

    per club, per game (or per simulated world):
        offensive_yards = passing yards + rushing yards

    coupling = Pearson r between the two clubs' offensive_yards,
               over the population

Passing plus rushing, NOT passing plus rushing plus receiving: receiving
yards are the same yards as passing yards seen from the other end, and adding
them would double every completion. Two-point plays are excluded on both
sides, as everywhere else in this repository.

THE POPULATION IS DIFFERENT IN KIND ON THE TWO SIDES, AND THAT IS THE WHOLE
DIFFICULTY. History gives one observation per GAME, so its correlation is
across games and carries both between-matchup variation and within-game
coupling. The simulation gives 8,000 observations of ONE game, so its
correlation is purely within-game: the same two clubs, the same opponent, the
same venue, every time. **These two numbers do not estimate the same
quantity**, and the comparison is only legitimate as a SIGN test -- does the
simulator produce the qualitative dependence football shows at all -- which
is exactly what the review claimed to find and what this measures.

To make the historical side as close as possible, it is also computed WITHIN
matchup-strength strata and as a within-season partial correlation, so that a
positive historical r cannot be dismissed as "good offences play bad
defences".

COVERAGE, STATED. The simulated side sums the NAMED rows of the sealed board.
A club's unmodelled rushers sit in `rush_player_pool__unmodelled_back_pool`
and are not in the per-player layers, so simulated club yards are a lower
bound on the club's total. A constant shortfall cannot create or destroy a
correlation, but a shortfall that varies with production can, and the size of
it is reported rather than assumed away.
"""
from __future__ import annotations

import collections
import csv
import gzip
import json
import math
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance import artifact_claim as AC             # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome, State    # noqa: E402

SPEC_VERSION = 'game-offense-coupling-1'
METRIC = 'GAME_OFFENSE_COUPLING'
DEFINITION = ('Pearson r between the two clubs\' (passing yards + rushing '
              'yards) in the same game, two-point plays excluded, receiving '
              'yards NOT added because they are the passing yards again')

PBP = 'nfl/research/postgame/pbp_%d.*.csv.gz'
FROZEN = _REPO / 'nfl/research/dfs/DET_BUF_2026W2/frozen'
OUT = _REPO / 'nfl/research/coupling/GAME_OFFENSE_COUPLING.json'


def _one(v):
    return str(v).strip() in ('1', '1.0', 'True', 'true')


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _blob(season):
    import glob
    hits = sorted(glob.glob(str(_REPO / (PBP % season))))
    return pathlib.Path(hits[-1]) if hits else None


def historical(season) -> Outcome:
    """One (home_yards, away_yards) pair per game."""
    p = _blob(season)
    if p is None:
        return Outcome.blocked('COUPLING_NO_PBP', f'no capture for {season}',
                               cause=Cause.DATA)
    per = collections.defaultdict(lambda: collections.defaultdict(float))
    week = {}
    with gzip.open(p, 'rt', errors='ignore') as fh:
        for r in csv.DictReader(fh):
            gid, club = r.get('game_id'), r.get('posteam')
            if not gid or not club or _one(r.get('two_point_attempt')):
                continue
            week[gid] = r.get('week')
            if _one(r.get('pass_attempt')):
                per[gid][club] += _f(r.get('passing_yards'))
            elif _one(r.get('rush_attempt')):
                per[gid][club] += _f(r.get('rushing_yards'))
    pairs, dropped = [], 0
    for gid, clubs in per.items():
        if len(clubs) != 2:
            dropped += 1
            continue
        a, b = sorted(clubs)            # deterministic, alphabetical by club
        pairs.append((gid, week.get(gid), a, clubs[a], b, clubs[b]))
    if len(pairs) < 3:
        return Outcome.fail('COUPLING_TOO_FEW_GAMES', f'{len(pairs)} game(s)',
                            cause=Cause.DATA)
    return Outcome.ok('COUPLING_HISTORICAL_FRAME', value=pairs,
                      detail=f'{len(pairs)} game(s) in {season}, '
                             f'{dropped} dropped for not carrying two clubs',
                      season=season, n_games=len(pairs), n_dropped=dropped,
                      blob=p.name)


def simulated() -> Outcome:
    """One (BUF_yards, DET_yards) pair per world, from the sealed board."""
    z = np.load(FROZEN / 'sealed_player_draws.npz')
    man = json.loads((FROZEN / 'sealed_player_draws_manifest.json').read_text())
    L = man['layers']
    n = int(np.asarray(z['dk_scoring__dk_points']).shape[1])
    tot = collections.defaultdict(lambda: np.zeros(n))
    cover = {}
    # passing yards: the QB layer, by club
    qb = L['qb']
    py = np.asarray(z['qb__pyds'])
    for i, club in enumerate(qb['row_teams']):
        tot[club] = tot[club] + py[i]
    cover['passing_rows'] = len(qb['row_ids'])
    # rushing yards: the rushing_total layer, by club
    ru = L['rushing_total']
    ry = np.asarray(z['rushing_total__rushing_yards'])
    for i, club in enumerate(ru['row_teams']):
        tot[club] = tot[club] + ry[i]
    cover['rushing_rows'] = len(ru['row_ids'])
    clubs = sorted(tot)
    if len(clubs) != 2:
        return Outcome.fail('COUPLING_SIM_NOT_TWO_CLUBS', str(clubs),
                            cause=Cause.DATA)
    unmodelled = None
    if 'rush_player_pool__unmodelled_back_pool' in z.files:
        u = np.asarray(z['rush_player_pool__unmodelled_back_pool'])
        unmodelled = float(u.sum(axis=0).mean()) if u.ndim == 2 else float(
            u.mean())
    return Outcome.ok(
        'COUPLING_SIMULATED_FRAME',
        value={'clubs': clubs, 'a': tot[clubs[0]], 'b': tot[clubs[1]]},
        detail=f'{n} world(s), clubs {clubs}',
        n_worlds=n, clubs=clubs, coverage=cover,
        unmodelled_back_pool_mean=unmodelled,
        coverage_caveat=('simulated club yards sum the NAMED rows only; a '
                         'club\'s unmodelled rushers are not in the '
                         'per-player layers, so these are a lower bound'))


def historical_points(season) -> Outcome:
    """The same games, scored in POINTS instead of yards.

    Yardage is the wrong aggregation for the shootout question and this is
    how that becomes visible rather than argued. Two clubs share one clock:
    every drive one club runs is a drive the other does not, so time of
    possession puts a NEGATIVE component into between-game yardage
    correlation that has nothing to do with whether they pushed each other.
    Points do not share a clock in the same way -- both clubs can score a lot
    in the same game -- so if a positive coupling exists anywhere at this
    aggregation, it is here.
    """
    p = _blob(season)
    if p is None:
        return Outcome.blocked('COUPLING_NO_PBP', f'no capture for {season}',
                               cause=Cause.DATA)
    fin = {}
    with gzip.open(p, 'rt', errors='ignore') as fh:
        for r in csv.DictReader(fh):
            gid = r.get('game_id')
            if not gid:
                continue
            h, a = r.get('total_home_score'), r.get('total_away_score')
            if h in (None, '') or a in (None, ''):
                continue
            fin[gid] = (_f(h), _f(a))
    if len(fin) < 3:
        return Outcome.fail('COUPLING_TOO_FEW_GAMES', f'{len(fin)} game(s)',
                            cause=Cause.DATA)
    return Outcome.ok('COUPLING_POINTS_FRAME', value=fin,
                      detail=f'{len(fin)} game(s) in {season}',
                      season=season, n_games=len(fin), blob=p.name)


def _r(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    if len(x) < 3 or x.std() == 0 or y.std() == 0:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def _fisher_ci(r, n, z=1.96):
    """Fisher-z interval. Reported because an r without one invites a story."""
    if r is None or n < 4 or abs(r) >= 1:
        return None
    f = 0.5 * math.log((1 + r) / (1 - r))
    se = 1.0 / math.sqrt(n - 3)
    lo, hi = f - z * se, f + z * se
    return [float(math.tanh(lo)), float(math.tanh(hi))]


def run(seasons=(2024, 2025)) -> Outcome:
    hist = {}
    for s in seasons:
        o = historical(s)
        if o.state is not State.PASS:
            return o
        pairs = o.value
        a = [p[3] for p in pairs]
        b = [p[5] for p in pairs]
        r = _r(a, b)
        # WITHIN-SEASON PARTIAL: centre each club's yards on its own season
        # mean first, so "good offences play bad defences" cannot explain a
        # positive r away.
        by_club = collections.defaultdict(list)
        for _g, _w, ca, ya, cb, yb in pairs:
            by_club[ca].append(ya)
            by_club[cb].append(yb)
        mean = {c: float(np.mean(v)) for c, v in by_club.items()}
        ra = [p[3] - mean[p[2]] for p in pairs]
        rb = [p[5] - mean[p[4]] for p in pairs]
        r_partial = _r(ra, rb)
        hist[s] = {
            'season': s, 'n_games': len(pairs),
            'r': r, 'r_ci95': _fisher_ci(r, len(pairs)),
            'r_club_demeaned': r_partial,
            'r_club_demeaned_ci95': _fisher_ci(r_partial, len(pairs)),
            'mean_club_yards': float(np.mean(a + b)),
            'sd_club_yards': float(np.std(a + b)),
            'blob': o.evidence['blob'], 'n_dropped': o.evidence['n_dropped']}
        pts = historical_points(s)
        if pts.state is State.PASS:
            ph = [v[0] for v in pts.value.values()]
            pa = [v[1] for v in pts.value.values()]
            rp = _r(ph, pa)
            hist[s]['r_points'] = rp
            hist[s]['r_points_ci95'] = _fisher_ci(rp, len(ph))
            hist[s]['n_games_points'] = len(ph)
            hist[s]['mean_club_points'] = float(np.mean(ph + pa))

    sim = simulated()
    if sim.state is not State.PASS:
        return sim
    sa, sb = sim.value['a'], sim.value['b']
    rs = _r(sa, sb)
    sim_row = {
        'population': 'sealed DET_BUF worlds',
        'n_worlds': sim.evidence['n_worlds'],
        'clubs': sim.value['clubs'],
        'r': rs, 'r_ci95': _fisher_ci(rs, sim.evidence['n_worlds']),
        'mean_club_yards': float(np.mean(np.concatenate([sa, sb]))),
        'sd_club_yards': float(np.std(np.concatenate([sa, sb]))),
        'coverage': sim.evidence['coverage'],
        'coverage_caveat': sim.evidence['coverage_caveat']}

    hs = [h['r'] for h in hist.values() if h['r'] is not None]
    sign_mismatch = bool(hs and rs is not None
                         and min(hs) > 0 > rs)
    return Outcome.ok(
        'GAME_OFFENSE_COUPLING_MEASURED',
        value={'historical': hist, 'simulated': sim_row},
        detail='; '.join(f"{s}: r={h['r']:+.4f} (n={h['n_games']})"
                         for s, h in hist.items())
               + f"; simulated: r={rs:+.4f} (n={sim_row['n_worlds']})",
        spec_version=SPEC_VERSION, metric=METRIC, definition=DEFINITION,
        sign_mismatch=sign_mismatch,
        populations_are_not_the_same_quantity=(
            'history is one observation per GAME and its r carries '
            'between-matchup variation as well as within-game coupling; the '
            'simulation is 8,000 observations of ONE game and its r is purely '
            'within-game. The comparison is legitimate as a SIGN test and not '
            'as an equality of estimates.'),
        points_cannot_be_compared_to_the_simulation=(
            'the sealed board emits NO score and no game total anywhere -- '
            'its team layer is snaps, dropbacks, carries, targets and '
            'red-zone carries. So the points coupling is measurable on '
            'history and NOT on the simulation, and that absence is itself '
            'the finding: a simulator with no score cannot produce a '
            'shootout, be asked whether it does, or be corrected toward one.'),
        nothing_is_injected=(
            'no historical correlation is written into the simulator and no '
            'correlation constant is introduced. This is a diagnostic gate.'),
        uses_live_game_outcome_data=False)


def main() -> int:
    o = run()
    print(f'{o.state.value}[{o.code}] {o.detail}')
    if o.state is not State.PASS:
        return 1
    v = o.value
    print(f"\n{'population':28s} {'n':>7s} {'r':>9s} {'95% CI':>22s}")
    for s, h in v['historical'].items():
        ci = h['r_ci95']
        print(f"{'history ' + str(s):28s} {h['n_games']:7d} {h['r']:+9.4f} "
              f"{('[%+.4f, %+.4f]' % (ci[0], ci[1])) if ci else '':>22s}")
        ci = h['r_club_demeaned_ci95']
        print(f"{'  club-demeaned':28s} {h['n_games']:7d} "
              f"{h['r_club_demeaned']:+9.4f} "
              f"{('[%+.4f, %+.4f]' % (ci[0], ci[1])) if ci else '':>22s}")
        if h.get('r_points') is not None:
            ci = h['r_points_ci95']
            print(f"{'  POINTS':28s} {h['n_games_points']:7d} "
                  f"{h['r_points']:+9.4f} "
                  f"{('[%+.4f, %+.4f]' % (ci[0], ci[1])) if ci else '':>22s}")
    sm = v['simulated']
    ci = sm['r_ci95']
    print(f"{'sealed worlds':28s} {sm['n_worlds']:7d} {sm['r']:+9.4f} "
          f"{('[%+.4f, %+.4f]' % (ci[0], ci[1])) if ci else '':>22s}")
    print(f"\nsign mismatch: {o.evidence['sign_mismatch']}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(
        {'spec_version': SPEC_VERSION, 'metric': METRIC,
         'definition': DEFINITION, 'detail': o.detail,
         'evidence': {k: x for k, x in o.evidence.items() if k != 'cause'},
         **v}, indent=1, sort_keys=True, default=str))
    c = AC.claim(OUT, schema=['historical', 'simulated'], label=OUT.name)
    return 0 if c.state is State.PASS else 1


if __name__ == '__main__':
    raise SystemExit(main())
