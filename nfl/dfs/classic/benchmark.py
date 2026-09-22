"""Large-pool equivalence and timing benchmark: optimized vs fe25d98.

Regenerates `nfl/research/readiness/CLASSIC_OPTIMIZER_BENCHMARK.json` with the
numbers it actually measured in the run that produced it. It is NOT part of
the test suite: `reference.py` is the slow implementation by construction, so
running it on a main-slate pool on every invocation would make the suite
minutes long. Run it deliberately whenever the optimizer changes.

An earlier version of this file printed its timings and claimed in its own
docstring to regenerate the artifact, and did not write anything. The JSON
therefore carried numbers from a different build of the optimizer than the one
on disk. Writing the file is now the last thing this script does, and it
refuses to write at all if the two implementations disagree.
"""
from __future__ import annotations

import json
import pathlib
import random
import sys
import time

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.dfs.classic import optimizer as O                          # noqa: E402
from nfl.dfs.classic import reference as REF                        # noqa: E402

ARTIFACT = _REPO / 'nfl/research/readiness/CLASSIC_OPTIMIZER_BENCHMARK.json'

MAIN_SPEC = [('QB', 2), ('RB', 5), ('WR', 8), ('TE', 3), ('DST', 1)]
SMALL_SPEC = [('QB', 2), ('RB', 4), ('WR', 6), ('TE', 3), ('DST', 1)]


def fixture(mod, *, n_teams, seed, spec, prefix, salary_hi, value_hi, base):
    rnd = random.Random(seed)
    teams = [f'{prefix}{n:02d}' for n in range(n_teams)]
    out, i = [], 0
    for ti, t in enumerate(teams):
        opp = teams[ti ^ 1] if (ti ^ 1) < n_teams else teams[ti - 1]
        for pos, k in spec:
            for j in range(k):
                i += 1
                out.append(mod.Player(
                    gsis_id=f'{t}-{pos}{j}', name=f'{t} {pos}{j}',
                    position=pos, team=t, opponent=opp,
                    salary=rnd.randrange(3000, salary_hi, 100),
                    dk_id=str(base + i),
                    value=round(rnd.uniform(value_hi[0], value_hi[1]), 3),
                    draw_row=i - 1))
    return out


def main_slate(mod):
    return fixture(mod, n_teams=24, seed=11, spec=MAIN_SPEC, prefix='T',
                   salary_hi=9800, value_hi=(2, 24), base=10000)


def small(mod, n_teams=6):
    return fixture(mod, n_teams=n_teams, seed=3, spec=SMALL_SPEC, prefix='S',
                   salary_hi=9500, value_hi=(3, 22), base=30000)


STACKED = dict(n_lineups=20, min_unique_players=2, global_max_exposure=0.5,
               qb_stack_min=2, bring_back_min=1, max_from_team=4,
               max_from_game=5)

GROUP = dict(n_lineups=3, min_unique_players=2, qb_stack_min=1,
             groups=[{'name': 'S00', 'min': 2,
                      'players': {f'S00-WR{j}' for j in range(6)}}])


def signature(outcome):
    v = outcome.value or (getattr(outcome, 'evidence', {}) or {}).get('value') \
        or {}
    return [(round(lu['value'], 9),
             tuple(sorted(x['gsis_id'] for x in lu['players'])))
            for lu in v.get('lineups', [])]


def run(name, build, kw):
    """Both implementations on the same fixture. Returns a result block."""
    block, sigs = {}, {}
    for tag, mod in (('optimized', O), ('reference_fe25d98', REF)):
        players = build(mod)
        c = mod.Constraints(**kw)
        t0 = time.time()
        out = mod.build_portfolio(players, c)
        el = time.time() - t0
        v = out.value or (out.evidence or {}).get('value') or {}
        sigs[tag] = signature(out)
        block[tag] = {
            'seconds': round(el, 2),
            'n_lineups': v.get('n_lineups'),
            'mean_overlap': (v.get('diversity') or {}).get('mean_overlap'),
            'best_value': (round(v['lineups'][0]['value'], 3)
                           if v.get('lineups') else None),
            'code': out.code,
        }
        print(f'{name:14s} {tag:18s} {el:8.2f}s  '
              f'n={block[tag]["n_lineups"]}  '
              f'best={block[tag]["best_value"]}', flush=True)
    block['identical_lineups'] = sigs['optimized'] == sigs['reference_fe25d98']
    ro, oo = block['reference_fe25d98']['seconds'], block['optimized']['seconds']
    block['speedup'] = round(ro / oo, 2) if oo else None
    print(f'{name:14s} IDENTICAL: {block["identical_lineups"]}  '
          f'speedup {block["speedup"]}x', flush=True)
    return block


def main():
    pool = main_slate(O)
    print(f'main-slate pool {len(pool)} players', flush=True)
    results = {
        'stacked_main_slate': run('main-slate', main_slate, STACKED),
        'group_minimum_4_teams': run('group-min',
                                     lambda m: small(m, n_teams=4), GROUP),
    }
    if not all(b['identical_lineups'] for b in results.values()):
        print('REFUSED: the two implementations disagree. Artifact not '
              'written.', file=sys.stderr)
        return 1
    doc = {
        'artifact': 'CLASSIC_OPTIMIZER_BENCHMARK',
        'spec_version': 'classic-optimizer-benchmark-2',
        'measured_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'what': 'equivalence and timing of the optimized Classic solver '
                'against reference.py, the frozen fe25d98 baseline. '
                'Regenerated deliberately, not on every test run, because '
                'the reference is the slow implementation by construction.',
        'reproduce': 'python3.12 nfl/dfs/classic/benchmark.py',
        'fixtures': {
            'stacked_main_slate': {
                'pool': len(pool), 'teams': 24, 'seed': 11,
                'spec': 'QB2 RB5 WR8 TE3 DST1 per team',
                'constraints': {k: v for k, v in STACKED.items()},
            },
            'group_minimum_4_teams': {
                'pool': len(small(O, n_teams=4)), 'teams': 4, 'seed': 3,
                'spec': 'QB2 RB4 WR6 TE3 DST1 per team',
                'constraints': {'n_lineups': 3, 'min_unique_players': 2,
                                'qb_stack_min': 1,
                                'groups': [{'name': 'S00', 'min': 2,
                                            'players': 'S00-WR0..WR5'}]},
                'why': 'the stacked decomposition multiplies a leaf-only '
                       'group test across every (QB, mate-count, '
                       'bring-back-count, distribution) cell. Before the '
                       'group-reachability prune this case took 36.62s here '
                       'against the reference 0.07s -- a 500x REGRESSION '
                       'that every correctness test passed, because the '
                       'answer was right and only the time was wrong.',
            },
        },
        'results': results,
        'exactness': 'each lineup in each portfolio matched the reference on '
                     'objective AND on player set, compared as a sorted id '
                     'set in portfolio order. The bounds are admissible -- '
                     'value and salary bounds can only over-estimate a '
                     'completion, and group reachability can only '
                     'over-estimate what a completion can contain -- so no '
                     'prune can discard a lineup better than the incumbent.',
        'target': 'owner target was 20 lineups on a realistic main-slate '
                  'pool, exact and deterministic, preferably under 30s',
    }
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(doc, indent=1) + '\n')
    back = json.loads(ARTIFACT.read_text())
    if back['results'] != results:
        print('REFUSED: artifact did not read back as written.',
              file=sys.stderr)
        return 1
    print(f'wrote {ARTIFACT.relative_to(_REPO)}', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
