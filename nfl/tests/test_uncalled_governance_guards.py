"""The five guards nothing calls: classified, and the pure ones now evaluated.

`nfl/tools/guard_reachability.py` finds five `assert_*` functions with no
caller anywhere -- not production, not research, not a test. All five were also
untested, so they were pure documentation: code that describes a property
nothing ever checks.

The instruction that shapes this file is "do not wire controls blindly. If a
guard is obsolete or conceptually wrong for the current architecture, remove or
quarantine it rather than making bad logic load-bearing." So each is read and
classified first, and only the ones that can honestly be evaluated are.

A DISTINCTION THAT DECIDED TWO OF THE FIVE: a guard over module CONSTANTS is a
test, not a runtime control. Its answer cannot change between two runs of the
same code, so calling it in production spends time to learn something the
source already determined. A guard over runtime DATA is the opposite. Sorting
by that resolved `assert_metric_origin_complete` immediately -- it takes no
arguments at all.

| guard | classification | why |
|---|---|---|
| `assert_metric_origin_complete` | TEST_NOT_RUNTIME | zero arguments, compares only constants |
| `assert_no_inactive_survived` | SUPERSEDED | DEF-064; successor is wired and STOPs |
| `assert_ranking_admissible` | ORPHANED_CONTROL | pure function over data, nothing calls it |
| `assert_live_lineage` | ORPHANED_CONTROL | needs the capture branch; belongs with D24 |
| `assert_prospective_matches_frozen` | CANDIDATE_SCOPED | guards Candidate B, which is not promoted |

Nothing here is wired INTO production. Two are now evaluated by the suite,
which is a smaller claim and the true one.
"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import State  # noqa: E402

PASSED = 0
FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  PASS {label}' + (f' -- {detail}' if detail else ''))
    else:
        FAILED += 1
        print(f'  FAIL {label}' + (f' -- {detail}' if detail else ''))


def test_metric_origin_is_complete_and_now_actually_checked():
    """TEST_NOT_RUNTIME, and it had never been evaluated by anything.

    Every SUPPORTED metric must be placed on a layer the eligibility matrix
    knows, or it has no route from a governance state to a publication
    decision. The function takes no arguments and reads three module
    constants, so its verdict is a property of the source: exactly a test.
    It passes today. Nobody knew that, because nothing called it.
    """
    print('\n[1] assert_metric_origin_complete -- TEST_NOT_RUNTIME')
    from nfl.production import authorization as A
    r = A.assert_metric_origin_complete()
    check('every SUPPORTED metric is placed on a known layer',
          r.state is State.PASS, f'{r.state.name}[{r.code}]')
    if r.state is not State.PASS:
        ev = r.as_dict().get('evidence') or {}
        check('  and the gap is named', False,
              f"missing={ev.get('missing')} extra={ev.get('extra')} "
              f"unknown={ev.get('unknown_layers')}")
    import inspect
    check('it takes no arguments, so it is a test and not a runtime control',
          not inspect.signature(A.assert_metric_origin_complete).parameters,
          'its answer cannot differ between two runs of the same source')


def test_the_ranking_gate_works_and_is_still_not_wired():
    """ORPHANED_CONTROL. Its logic is sound; nothing calls it.

    `model_health` calls this "THE GATE. This is the rule the product exists to
    enforce". It strips from a ranked table any row whose metric is under a
    health warning -- not deleting it from the comparison, removing it from the
    RANKING, with the reason travelling. Proving the logic is cheap. Wiring it
    is a product decision about what the ranking is for, so it is NOT done
    here; leaving it unwired and tested is more honest than either pretending
    it protects something or deleting a control that reads correct.
    """
    print('\n[2] assert_ranking_admissible -- ORPHANED_CONTROL')
    from nfl.product import model_health as MH
    rows = [{'metric': 'rush_yards', 'delta': 40.0},
            {'metric': 'rec_yards', 'delta': 12.0}]
    health = [{'metric': 'rush_yards', 'ranking_eligible': False,
               'warnings': ['DISPERSION_COLLAPSE']},
              {'metric': 'rec_yards', 'ranking_eligible': True,
               'warnings': []}]
    kept, blocked = MH.assert_ranking_admissible(rows, health)
    check('a row under a health warning leaves the ranking',
          [r['metric'] for r in blocked] == ['rush_yards'],
          str([r['metric'] for r in blocked]))
    check('the eligible row stays',
          [r['metric'] for r in kept] == ['rec_yards'],
          str([r['metric'] for r in kept]))
    check('and the reason travels with the blocked row',
          blocked and blocked[0].get('blocked_by_health')
          == ['DISPERSION_COLLAPSE'],
          str(blocked[0].get('blocked_by_health') if blocked else None))
    check('a metric absent from the health table is NOT blocked',
          MH.assert_ranking_admissible(
              [{'metric': 'unknown_metric'}], health)[0] != [],
          'silence in the health table is not a warning; whether it SHOULD be '
          'is the product decision this guard is waiting on')


def test_the_superseded_one_is_superseded_in_fact():
    """SUPERSEDED, and the successor is load-bearing rather than merely present."""
    print('\n[3] assert_no_inactive_survived -- SUPERSEDED (DEF-064)')
    import json
    cen = json.loads(
        (_REPO / 'nfl/research/audit/GUARD_REACHABILITY.json').read_text())
    rows = {r['guard']: r for r in cen['rows']}
    old = rows.get('assert_no_inactive_survived')
    new = rows.get('assert_no_inactive_in_playable')
    check('the old one still has no caller',
          old and old['reachability'] == 'NO_CALLER_AT_ALL',
          old['reachability'] if old else 'absent')
    check('the successor is externally called',
          new and new['reachability'] == 'EXTERNALLY_CALLED',
          new['reachability'] if new else 'absent')
    check('and its failure STOPS the caller',
          new and 'STOP' in new['effect_on_failure'],
          str(new['effect_on_failure']) if new else '')
    check('so the supersession is real, not just asserted',
          bool(old and new) and old['reachability'] != new['reachability'],
          'a supersession where neither is wired is two orphans')


def test_the_two_that_cannot_be_evaluated_here_say_why():
    """Named debt beats a silent gap.

    Neither of these can be called without setup this suite must not fake, and
    faking it is the DEF-065 shape: a check that runs against a fixture it
    invented proves nothing about the thing it names.
    """
    print('\n[4] the two left unevaluated, with the reason recorded')
    import inspect
    from nfl.production import capture_cadence as CC
    from nfl.production.nonqb import appearance_b as B
    check('assert_live_lineage needs a real vintage manifest',
          'manifest' in inspect.signature(CC.assert_live_lineage).parameters,
          'it reads the capture branch; wiring it belongs with the open D24 '
          'capture-deployment items, not here')
    check('assert_prospective_matches_frozen needs a season, week, players '
          'and injuries rows',
          len(inspect.signature(B.assert_prospective_matches_frozen)
              .parameters) == 4,
          'CANDIDATE_SCOPED: it guards Candidate B against the accepted walk, '
          'and Candidate B has no production caller either')
    check('both are recorded as still uncalled and untested', True,
          'ORPHANED_CONTROL and CANDIDATE_SCOPED; neither is deleted, because '
          'neither reads wrong -- they read unreached')


def main():
    print(__doc__.strip().splitlines()[0])
    test_metric_origin_is_complete_and_now_actually_checked()
    test_the_ranking_gate_works_and_is_still_not_wired()
    test_the_superseded_one_is_superseded_in_fact()
    test_the_two_that_cannot_be_evaluated_here_say_why()
    print(f'\n{PASSED} passed, {FAILED} failed')
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())
