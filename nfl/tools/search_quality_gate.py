#!/usr/bin/env python3.12
"""Search-quality regression gate. The owner's placeholder portfolio is the floor.

OWNER RULING, 2026-09-27. "Claude should treat that file as a minimum search-quality
regression target going forward. If a new optimizer cannot at least recover that quality on
the same pool and projections, it should fail the build."

So this gate is deliberately RED today. On 2026-09-27 the frontier established that a
hand/FC-built portfolio beat the optimizer on its own yardstick:

    best single lineup   owner 171.59   optimizer 169.48
    portfolio mean       owner 167.35   optimizer 163.44 (unconstrained)

An optimizer that cannot find a lineup which demonstrably EXISTS in a benchmark file, on the
same player pool and the same projections, is not trustworthy. That is a search failure, not
a modelling opinion, and it is measurable without any football judgement at all -- which is
what makes it a good build gate.

WHY THIS IS A FAIR TEST. Same pool, same FC numbers, same legality rules, same 48 entries.
The benchmark is not allowed any advantage: it is scored by the same function, and where it
rosters a player with no FC row those points are simply absent, which biases the benchmark
DOWN. It still wins.

THE GATE CLEARS when the optimizer matches or beats both figures. Until then it stays RED and
no search change may be described as an improvement without moving these two numbers.
"""
from __future__ import annotations

import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Outcome  # noqa: E402

SPEC_VERSION = 'search-quality-gate-1'

FRONTIER = _REPO / 'nfl/dfs/salaries/DK_WEEK3_PORTFOLIO_FRONTIER.json'
OUT = _REPO / 'nfl/dfs/salaries/SEARCH_QUALITY_GATE.json'

#: Frozen 2026-09-27 from the owner's DKEntries-62 FC placeholder portfolio, scored on the
#: same pool and the same FC numbers as the optimizer. These are the floor, not a target to
#: approach -- the optimizer must MATCH OR BEAT both.
BENCHMARK = {
    'source': 'nfl/dfs/salaries/raw/OWNER_PLACEHOLDERS_FC_48_2026W3.csv',
    'source_sha256': '13ce2da14da94f961f8288f46faabeea016394290594338ca77124297f216e53',
    'frozen_at': '2026-09-27',
    'best_single_lineup': 171.59,
    'portfolio_mean': 167.35,
    'n_lineups': 48,
    'projection_source': 'EXTERNAL_FC_FALLBACK',
    'scored_by': 'the same function that scores the optimizer, with no advantage given',
    'downward_bias_note': (
        'where the benchmark rosters a player with no FantasyCruncher row, those points are '
        'absent from its total. The benchmark is therefore understated and still wins.'),
}

#: The optimizer must be compared UNCONSTRAINED. A diversified mode legitimately scores
#: lower, so measuring it against this floor would confuse a deliberate trade-off with a
#: search defect -- the exact conflation that produced the wrong diagnosis on 2026-09-27.
COMPARISON_MODE = 'PROJECTION_MAX'


def evaluate(frontier=None):
    if frontier is None:
        if not FRONTIER.exists():
            return Outcome.fail('FRONTIER_ABSENT',
                                'no frontier artifact to read the optimizer result from')
        frontier = json.loads(FRONTIER.read_text())
    mode = (frontier.get('modes') or {}).get(COMPARISON_MODE)
    if not mode or mode.get('state') != 'OK':
        return Outcome.fail('OPTIMIZER_RESULT_ABSENT',
                            f'{COMPARISON_MODE} produced no usable portfolio')
    opt_best = max(mode['proj_max'],
                   (frontier.get('optimum_legal_lineup') or {}).get('proj_total', 0)
                   if (frontier.get('optimum_legal_lineup') or {}).get('source')
                   != 'OWNER_BENCHMARK_LINEUP' else 0)
    # if the reference came FROM the benchmark it is not the optimizer's achievement
    ref = frontier.get('optimum_legal_lineup') or {}
    if ref.get('source') == 'OWNER_BENCHMARK_LINEUP':
        opt_best = max(mode['proj_max'],
                       (ref.get('beaten_by_benchmark') or {}).get('search_best', 0))
    opt_mean = mode['proj_mean']

    checks = [
        {'check': 'best_single_lineup',
         'benchmark': BENCHMARK['best_single_lineup'], 'optimizer': round(opt_best, 2),
         'shortfall': round(BENCHMARK['best_single_lineup'] - opt_best, 2),
         'pass': opt_best >= BENCHMARK['best_single_lineup'] - 1e-9,
         'why': ('the optimizer must find a lineup at least as good as one that provably '
                 'exists in the benchmark, on the same pool')},
        {'check': 'portfolio_mean',
         'benchmark': BENCHMARK['portfolio_mean'], 'optimizer': round(opt_mean, 2),
         'shortfall': round(BENCHMARK['portfolio_mean'] - opt_mean, 2),
         'pass': opt_mean >= BENCHMARK['portfolio_mean'] - 1e-9,
         'why': ('unconstrained, the optimizer must match the benchmark portfolio mean. A '
                 'diversified mode may legitimately score lower and is NOT measured here')},
    ]
    failed = [c for c in checks if not c['pass']]
    art = {
        'artifact': 'SEARCH_QUALITY_GATE', 'spec_version': SPEC_VERSION,
        'owner_ruling': ('if a new optimizer cannot at least recover the benchmark quality '
                         'on the same pool and projections, it fails the build'),
        'benchmark': BENCHMARK, 'comparison_mode': COMPARISON_MODE,
        'checks': checks,
        'state': 'RED' if failed else 'GREEN',
        'n_failed': len(failed),
        'verdict': (
            f'SEARCH_NOT_TRUSTWORTHY: {len(failed)} of {len(checks)} floors unmet. '
            f'No search change may be called an improvement without moving these numbers.'
            if failed else
            'SEARCH_RECOVERS_BENCHMARK: both floors met on the same pool and projections.'),
        'DELIBERATELY_RED_TODAY': (
            'this gate is expected to fail until the optimizer improves. A gate that passed '
            'on the day it was written would not be measuring anything.'),
    }
    OUT.write_text(json.dumps(art, indent=2) + '\n')
    if failed:
        return Outcome.fail(
            'SEARCH_QUALITY_BELOW_BENCHMARK',
            f'{len(failed)} floor(s) unmet: ' + '; '.join(
                f'{c["check"]} {c["optimizer"]} vs {c["benchmark"]} '
                f'(short {c["shortfall"]})' for c in failed),
            checks=checks, state='RED')
    return Outcome.ok('SEARCH_QUALITY_AT_BENCHMARK', art,
                      'both floors met', checks=checks)


def main() -> int:
    r = evaluate()
    print(r)
    art = json.loads(OUT.read_text()) if OUT.exists() else {}
    for c in art.get('checks', ()):
        mark = 'PASS' if c['pass'] else 'FAIL'
        print(f'  {mark}  {c["check"]:20s} optimizer {c["optimizer"]:7.2f}  '
              f'benchmark {c["benchmark"]:7.2f}  short {c["shortfall"]:+6.2f}')
    print(f'\n{art.get("verdict", "")}')
    return 0 if art.get('state') == 'GREEN' else 1


if __name__ == '__main__':
    raise SystemExit(main())
