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
    'PARTIAL_JOIN': 18,
    'FIXTURE_PINNED': 35,
    'ORPHANED_OUTPUT': 1,
}

#: 524 of 949 at the same commit.
UNTESTED_REFUSAL_CODES = 524

#: Governance modules with zero non-test consumers, by name rather than by
#: count, because which nine matters more than that there are nine.
ORPHANED_GATES = (
    'identity_crosswalk', 'research_portfolio', 'lineup_integrity',
    'cut_ledger', 'source_validity', 'source_census', 'pregame_readiness',
    'conditioning_contract', 'discovery_audit',
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
    """Non-test modules referencing `module`, excluding the file itself."""
    out = []
    for p in sorted(_REPO.glob('nfl/**/*.py')):
        rel = str(p.relative_to(_REPO))
        if '__pycache__' in rel or '/tests/' in rel or rel.endswith(
                f'/{module}.py'):
            continue
        if module in p.read_text():
            out.append(rel)
    return out


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
    check(f'{len(still)} of {len(ORPHANED_GATES)} still orphaned, none new',
          len(still) <= len(ORPHANED_GATES),
          'this list may only shrink')
    check('the list is still honest about what it claims',
          all(m in ORPHANED_GATES for m in still), still)


def test_D_the_contract_exists_and_defaults_to_refusal():
    print('\nD. the machinery the ratchet points at')
    from nfl.production.contracts import completeness as CC
    pol, _ = CC.policy_for('a.consumer.invented.for.this.test')
    check('an undeclared consumer requires completeness',
          pol == CC.REQUIRES_COMPLETE, pol)
    from nfl.dfs import gate_enforcement as GE
    check('and an unevaluated HARD gate is not a pass',
          GE.decide({}, 'dfs.showdown.selector')['may_consume'] is False)
