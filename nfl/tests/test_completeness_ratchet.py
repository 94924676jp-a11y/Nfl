"""The counts in the 2026-09-25 audit may fall. They may not rise.

WHY A RATCHET AND NOT A TARGET

Every number here is bad. 18 partial joins, 35 modules pinned to a September
fixture, 9 gates nobody calls, 524 refusal codes no test mentions. Asserting
them at zero would fail the suite today and be deleted by whoever is next in a
hurry, which is how a standard becomes a comment.

So the assertion is direction, not level. The count at the moment of the audit
is written down, and the suite fails if the next change makes any of them worse.
That converts "we should fix this" into "you cannot add another one", which is
the only version that survives contact with a deadline.

WHEN A NUMBER GOES DOWN, LOWER IT HERE IN THE SAME COMMIT. A ratchet left above
the true count is slack, and slack is where the next one hides.
"""
from __future__ import annotations

import ast
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import cross_layer_audit as X                   # noqa: E402

PASSED = 0
FAILED = 0

#: Measured at 8d63b6c on 2026-09-25. See
#: nfl/research/audit/2026-09-25_CONSOLIDATED_DEFECT_LEDGER.md
BASELINE = {
    # LOWERED 2026-09-26 from 18/35/1 measured at 8d63b6c. This file's own rule
    # is that a number going down is lowered in the same commit, because "a
    # ratchet left above the true count is slack, and slack is where the next
    # one hides" -- and it had been carrying 13 of slack.
    'PARTIAL_JOIN': 16,
    'FIXTURE_PINNED': 24,
    'ORPHANED_OUTPUT': 1,
}

#: 524 of 949 at 8d63b6c; LOWERED 2026-09-26 to the measured 511 of 942.
UNTESTED_REFUSAL_CODES = 511

#: Governance modules with zero non-test consumers, by name rather than by
#: count, because which nine matters more than that there are nine.
ORPHANED_GATES = (
    'identity_crosswalk', 'research_portfolio', 'lineup_integrity',
    'cut_ledger', 'source_validity', 'source_census', 'pregame_readiness',
    'conditioning_contract', 'discovery_audit',
)


#: Modules defining an assert_* guard that nothing imports, measured
#: 2026-09-26. DISCOVERED, not declared -- see _orphaned_guard_modules. This is
#: the count the ratchet holds; the names are kept only so a failure can say
#: WHICH one is new.
ORPHANED_GUARD_MODULES = 19
_KNOWN_ORPHANED_GUARDS = (
    'nfl/adapters/routes_source.py', 'nfl/capture/deferral_escalation.py',
    'nfl/capture/manifest_store.py', 'nfl/capture/source_discovery.py',
    'nfl/dfs/identity_crosswalk.py',
    'nfl/dfs/salaries/postinactives_board.py', 'nfl/dfs/scoring/site_rules.py',
    'nfl/dfs/showdown/universe_contract.py', 'nfl/product/model_health.py',
    'nfl/production/capture_cadence.py',
    'nfl/production/conditioning_contract.py', 'nfl/production/dependence.py',
    'nfl/production/gate_ids.py', 'nfl/production/nonqb/appearance_b.py',
    'nfl/production/workflow/stages.py', 'nfl/prospective/nfl1_readiness.py',
    'nfl/prospective/q9shadow/armpolicy.py',
    'nfl/prospective/q9shadow/reuse.py', 'nfl/truth/run_input.py',
)


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


def _consumers_of(module: str) -> list:
    """Non-test modules that IMPORT `module`. By import, not by mention.

    This was a substring search, and a substring search calls a module consumed
    when another file merely names it in a docstring. Measured 2026-09-26, that
    made FOUR of the nine look wired -- source_census, pregame_readiness,
    conditioning_contract and discovery_audit -- so test_C printed "WIRED ... now
    has a consumer; remove it from ORPHANED_GATES" for them. pregame_readiness's
    only "consumer" names it in two docstrings and a dict key, and A-02's
    prescribed fix for the whole finding is to WIRE pregame_readiness. The test
    was advising its removal from the tracked list on the strength of prose.

    Measured by real imports, all nine have zero consumers and the declared list
    is honest. DEF-080.
    """
    out = []
    for p in sorted(_REPO.glob('nfl/**/*.py')):
        rel = str(p.relative_to(_REPO))
        if '__pycache__' in rel or '/tests/' in rel or rel.endswith(
                f'/{module}.py'):
            continue
        try:
            tree = ast.parse(p.read_text(errors='replace'))
        except SyntaxError:
            continue
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom) and (
                    (n.module or '').endswith(module)
                    or any(a.name == module for a in n.names)):
                out.append(rel)
                break
            if isinstance(n, ast.Import) and any(
                    a.name.endswith(module) for a in n.names):
                out.append(rel)
                break
    return out


def _orphaned_guard_modules() -> list:
    """Modules that DEFINE an assert_* guard and that nothing imports.

    WHY THIS EXISTS. test_C could not fail. `still` was built by filtering
    ORPHANED_GATES, so `len(still) <= len(ORPHANED_GATES)` and
    `all(m in ORPHANED_GATES for m in still)` were both true by construction.
    Run under two states that should have failed it -- all nine suddenly wired,
    and a tenth orphaned module existing -- it returned 2 passed, 0 failed both
    times. Its message said "none new" while it never looked outside the list.

    So the population is DISCOVERED here rather than declared, which is what
    makes the ratchet below capable of failing. It is a different question from
    ORPHANED_GATES: those nine are governance modules chosen by hand and seven of
    them define no assert_* function at all, so this measure does not replace
    them and neither list subsumes the other.

        ONE PASS, not one pass per candidate. The first version called
    _consumers_of() for each of ~180 modules and each of those re-parsed every
    file in the repository, so it took minutes. This file's own warning is that a
    standard nobody maintains gets deleted by whoever is next in a hurry, and a
    ratchet slow enough to be annoying is exactly that.
    """
    defines, imported = [], set()
    for p in sorted(_REPO.glob('nfl/**/*.py')):
        rel = str(p.relative_to(_REPO))
        if '__pycache__' in rel:
            continue
        try:
            tree = ast.parse(p.read_text(errors='replace'))
        except SyntaxError:
            continue
        research_or_test = '/tests/' in rel or '/research/' in rel
        if not research_or_test and any(
                isinstance(n, ast.FunctionDef)
                and n.name.startswith('assert_') for n in tree.body):
            defines.append((p.stem, rel))
        # Tests do not count as consumers, and a module importing itself is not
        # a consumer of itself.
        if research_or_test:
            continue
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom):
                if n.module:
                    imported.add((n.module.rsplit('.', 1)[-1], rel))
                for a in n.names:
                    imported.add((a.name, rel))
            elif isinstance(n, ast.Import):
                for a in n.names:
                    imported.add((a.name.rsplit('.', 1)[-1], rel))
    consumed = {stem for stem, importer in imported
                if not importer.endswith(f'/{stem}.py')}
    return sorted(rel for stem, rel in defines if stem not in consumed)


def test_A_cross_layer_relations_do_not_worsen():
    print('\nA. no new partial join, fixture pin or orphaned family')
    counts = X.relation_counts()
    for kind, cap in sorted(BASELINE.items()):
        n = counts.get(kind, 0)
        check(f'{kind} {n} <= {cap}', n <= cap,
              f'rose to {n}; the audit measured {cap}. Route the new join '
              f'through nfl/production/contracts/completeness.py, or lower '
              f'the baseline if you removed one.')
        if n < cap:
            print(f'       NOTE {kind} improved to {n}; lower BASELINE '
                  f'in this commit.')


def test_B_untested_refusal_codes_do_not_rise():
    print('\nB. a new refusal arrives with the test that proves it')
    untested, total = X.untested_refusal_codes()
    check(f'untested refusal codes {len(untested)} <= '
          f'{UNTESTED_REFUSAL_CODES} (of {total})',
          len(untested) <= UNTESTED_REFUSAL_CODES,
          f'rose to {len(untested)}. A refusal path nothing exercises is an '
          f'untested guarantee.')


def test_C_the_orphaned_gates_are_named_and_tracked():
    print('\nC. a gate nothing calls is documentation')
    still = [m for m in ORPHANED_GATES if not _consumers_of(m)]
    wired = [m for m in ORPHANED_GATES if m not in still]
    for m in wired:
        print(f'       WIRED {m} now has a consumer; remove it from '
              f'ORPHANED_GATES.')
    # THESE TWO USED TO BE THE WHOLE CHECK AND NEITHER COULD FAIL: `still` is a
    # filtered subset of ORPHANED_GATES, so both were true by construction. They
    # are kept because a shrinking list is still worth reporting, and the
    # failable assertions are below.
    check(f'{len(still)} of {len(ORPHANED_GATES)} still orphaned',
          len(still) <= len(ORPHANED_GATES),
          'this list may only shrink')
    check('the list is still honest about what it claims',
          all(m in ORPHANED_GATES for m in still), still)

    # AND THE PART THAT CAN ACTUALLY FAIL. The population is discovered, so a
    # NEW orphaned control fails the suite instead of passing unseen.
    found = _orphaned_guard_modules()
    check(f'orphaned guard modules {len(found)} <= {ORPHANED_GUARD_MODULES}',
          len(found) <= ORPHANED_GUARD_MODULES,
          f'rose to {len(found)}. A module defining an assert_* guard that '
          f'nothing imports is documentation. New ones: '
          f'{[f for f in found if f not in _KNOWN_ORPHANED_GUARDS]}')
    if len(found) < ORPHANED_GUARD_MODULES:
        print(f'       NOTE orphaned guard modules improved to {len(found)}; '
              f'lower ORPHANED_GUARD_MODULES in this commit.')


def test_D_the_contract_exists_and_defaults_to_refusal():
    print('\nD. the machinery the ratchet points at')
    from nfl.production.contracts import completeness as CC
    pol, _ = CC.policy_for('a.consumer.invented.for.this.test')
    check('an undeclared consumer requires completeness',
          pol == CC.REQUIRES_COMPLETE, pol)
    from nfl.dfs import gate_enforcement as GE
    check('and an unevaluated HARD gate is not a pass',
          GE.decide({}, 'dfs.showdown.selector')['may_consume'] is False)
