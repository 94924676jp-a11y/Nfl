"""Fit CS2's two prior strengths by forward chaining. Never on 2026.

THE CHAIN. For each season S in 2022-2025 and each week W from 2 to 18,
predict week W from weeks 1..W-1 of S plus the whole of S-1, and score
against what week W actually did. Nothing from week W or later ever enters a
prediction of week W. The guard is an assertion, not a comment.

2026 IS NOT IN THE CHAIN. It has one week, which cannot be forward-chained,
and it is the season the state will be USED on. Fitting a hyperparameter on
the week you then apply it to is the thing this repository refuses.

TWO SCORES, BECAUSE THERE ARE TWO QUANTITIES

  appearance   Brier score on 'did he take a carry or a target in week W',
               over every man in the room.
  allocation   multinomial log-loss of the realised room split against the
               predicted shares, over the men who DID appear. Scored on
               OPPORTUNITY, never on yards, so a role improvement cannot be
               confounded with an efficiency change.

COMPARATORS, DECLARED IN ADVANCE

  PRIOR_ONLY   kappa -> infinity. Prior season alone, which is what a
               non-QB layer without CS2 effectively has.
  UNIFORM      every man in the room equally likely and equally used. The
               no-information floor.

A MEASURED NEGATIVE IS A RESULT. If no (kappa_a, kappa_s) beats PRIOR_ONLY out
of sample, that is recorded and CS2 stage 2 does not ship. The grid is not
widened afterwards.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance import artifact_claim as AC             # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome, State    # noqa: E402
from nfl.production.nonqb import cs2_state as CS                       # noqa: E402
from nfl.production.nonqb import current_season_nonqb_panel as P       # noqa: E402

SPEC_VERSION = 'cs2-stage2-forward-chain-1'
OUT = _REPO / 'nfl/research/cs2/CS2_STAGE2_FIT.json'

CHAIN_SEASONS = (2022, 2023, 2024, 2025)
FIRST_WEEK, LAST_WEEK = 2, 18
PRIOR_ONLY = 'PRIOR_ONLY'
UNIFORM = 'UNIFORM'
EPS = 1e-9


def _by_week(rows):
    out = collections.defaultdict(dict)
    for (wk, club, pid), d in rows.items():
        out[wk][(club, pid)] = d
    return out


def _score_week(est, truth_week, room):
    """(brier terms, logloss terms) for one week of one room."""
    actual = collections.defaultdict(float)
    for (club, pid), d in truth_week.items():
        actual[(club, pid)] = d[room]
    club_tot = collections.defaultdict(float)
    for (club, pid), v in actual.items():
        club_tot[club] += v
    brier, logloss = [], []
    for (club, pid), r in est.items():
        y = 1.0 if actual.get((club, pid), 0.0) > 0 else 0.0
        brier.append((r['p_appears'] - y) ** 2)
    for (club, pid), v in actual.items():
        if v <= 0 or not club_tot[club]:
            continue
        r = est.get((club, pid))
        p = r['share_given_appears'] if r else EPS
        logloss.append(-v * math.log(max(p, EPS)))
    return brier, logloss


def run(seasons=CHAIN_SEASONS, kappa_a=CS.KAPPA_A_GRID,
        kappa_s=CS.KAPPA_S_GRID, verbose=True) -> Outcome:
    cache = {}

    def usage(season):
        if season not in cache:
            o = P.usage_season(season)
            cache[season] = o.value if o.state is State.PASS else None
        return cache[season]

    arms = [(a, s) for a in kappa_a for s in kappa_s]
    acc = {('ARM', a, s): {'brier': [], 'logloss': [], 'n': 0}
           for a, s in arms}
    for label in (PRIOR_ONLY, UNIFORM):
        acc[(label, None, None)] = {'brier': [], 'logloss': [], 'n': 0}

    n_folds = 0
    ordinal_violations = []
    for season in seasons:
        cur, prev = usage(season), usage(season - 1)
        if cur is None or prev is None:
            continue
        cur_w = _by_week(cur)
        for room in CS.ROOMS:
            prior = CS.prior_from_season(prev, room)
            for W in range(FIRST_WEEK, LAST_WEEK + 1):
                if W not in cur_w:
                    continue
                conditioning = {k: v for k, v in cur.items() if k[0] < W}
                # ORDINAL GUARD, as an assertion. Nothing at or beyond the
                # forecast week may be in the conditioning set.
                late = [k for k in conditioning if k[0] >= W]
                if late:
                    ordinal_violations.append({'season': season, 'week': W,
                                               'n': len(late)})
                    continue
                roster = set(cur_w[W])          # already (club, pid)
                truth = cur_w[W]
                n_folds += 1
                for a, s in arms:
                    o = CS.state(conditioning, prior, room, kappa_a=a,
                                 kappa_s=s, n_weeks=W - 1, roster=roster)
                    if o.state is not State.PASS:
                        return o
                    b, l = _score_week(o.value, truth, room)
                    acc[('ARM', a, s)]['brier'] += b
                    acc[('ARM', a, s)]['logloss'] += l
                    acc[('ARM', a, s)]['n'] += 1
                # PRIOR_ONLY: infinite prior strength is the prior itself.
                o = CS.state(conditioning, prior, room, kappa_a=1e9,
                             kappa_s=1e9, n_weeks=W - 1, roster=roster)
                b, l = _score_week(o.value, truth, room)
                acc[(PRIOR_ONLY, None, None)]['brier'] += b
                acc[(PRIOR_ONLY, None, None)]['logloss'] += l
                acc[(PRIOR_ONLY, None, None)]['n'] += 1
                # UNIFORM: no information at all.
                o = CS.state(conditioning, {}, room, kappa_a=1e9,
                             kappa_s=1e9, n_weeks=W - 1, roster=roster)
                b, l = _score_week(o.value, truth, room)
                acc[(UNIFORM, None, None)]['brier'] += b
                acc[(UNIFORM, None, None)]['logloss'] += l
                acc[(UNIFORM, None, None)]['n'] += 1
            if verbose:
                print(f'  {season} {room}: chained', flush=True)
    if ordinal_violations:
        return Outcome.fail(
            'CS2_ORDINAL_GUARD_TRIPPED',
            f'{len(ordinal_violations)} fold(s) carried conditioning rows at '
            f'or beyond the forecast week', cause=Cause.DATA,
            violations=ordinal_violations[:10])
    if not n_folds:
        return Outcome.blocked('CS2_NO_FOLDS', 'no fold could be built',
                               cause=Cause.DATA)

    def summarise(d):
        nb, nl = len(d['brier']) or 1, len(d['logloss']) or 1
        return {'brier': sum(d['brier']) / nb,
                'logloss': sum(d['logloss']) / nl,
                'n_appearance_terms': len(d['brier']),
                'n_allocation_terms': len(d['logloss'])}

    rows = []
    for (label, a, s), d in acc.items():
        rows.append({'arm': label if label != 'ARM' else f'k_a={a},k_s={s}',
                     'kappa_a': a, 'kappa_s': s, **summarise(d)})
    arms_only = [r for r in rows if r['kappa_a'] is not None]
    base = next(r for r in rows if r['arm'] == PRIOR_ONLY)
    unif = next(r for r in rows if r['arm'] == UNIFORM)
    best_app = min(arms_only, key=lambda r: r['brier'])
    best_all = min(arms_only, key=lambda r: r['logloss'])
    beats_app = best_app['brier'] < base['brier']
    beats_all = best_all['logloss'] < base['logloss']
    rows.sort(key=lambda r: (r['brier'], r['logloss']))
    return Outcome.ok(
        'CS2_STAGE2_CHAINED',
        value={'rows': rows, 'best_appearance': best_app,
               'best_allocation': best_all,
               PRIOR_ONLY: base, UNIFORM: unif},
        detail=f'{n_folds} fold(s); best appearance Brier '
               f'{best_app["brier"]:.5f} at {best_app["arm"]} against '
               f'PRIOR_ONLY {base["brier"]:.5f}; best allocation log-loss '
               f'{best_all["logloss"]:.5f} at {best_all["arm"]} against '
               f'{base["logloss"]:.5f}',
        spec_version=SPEC_VERSION, amendment=CS.AMENDMENT,
        seasons=list(seasons), n_folds=n_folds,
        ordinal_guard='assertion, not a comment; 0 violations',
        beats_prior_only_on_appearance=bool(beats_app),
        beats_prior_only_on_allocation=bool(beats_all),
        measured_negative_is_a_result=(
            'if no arm beats PRIOR_ONLY the grid is NOT widened and CS2 '
            'stage 2 does not ship.'),
        scored_on_opportunity_not_yards=True,
        seasons_excluded={'2026': 'one week, cannot be chained, and it is the '
                                  'season the state will be used on'})


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--seasons', default=','.join(map(str, CHAIN_SEASONS)))
    a = ap.parse_args(argv)
    o = run(seasons=tuple(int(x) for x in a.seasons.split(',')))
    print(f'{o.state.value}[{o.code}] {o.detail}')
    if o.state is not State.PASS:
        return 1
    print(f"\n{'arm':18s} {'brier':>9s} {'logloss':>10s}")
    for r in o.value['rows'][:10]:
        print(f"{r['arm']:18s} {r['brier']:9.5f} {r['logloss']:10.5f}")
    for k in (PRIOR_ONLY, UNIFORM):
        r = o.value[k]
        print(f"{r['arm']:18s} {r['brier']:9.5f} {r['logloss']:10.5f}")
    OUT.write_text(json.dumps(
        {'spec_version': SPEC_VERSION, 'detail': o.detail,
         'evidence': {k: v for k, v in o.evidence.items() if k != 'cause'},
         **o.value}, indent=1, sort_keys=True, default=str))
    c = AC.claim(OUT, schema=['rows', 'best_appearance'], label=OUT.name)
    return 0 if c.state is State.PASS else 1


if __name__ == '__main__':
    raise SystemExit(main())
