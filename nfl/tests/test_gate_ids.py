"""Gates are referenced by name, readiness is four states, and an UNDECIDED
gate blocks."""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production import gate_ids as G                            # noqa: E402
from nfl.production import ownership_audit as OA                    # noqa: E402
from sportsplatform.governance.outcome import State                 # noqa: E402

PASSED = 0
FAILED = 0
NOT_EXECUTED = []


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


def test_A_identity_is_the_name():
    print('\nA. a number is not an identity')
    o = G.get('SINGLE_ADJUSTMENT_OWNERSHIP')
    check('a declared gate resolves by name', o.state is State.PASS,
          f'{o.state}[{o.code}]')
    bad = G.get('11')
    check('a bare number does NOT resolve',
          bad.state is State.FAIL and bad.code == 'UNKNOWN_GATE_ID',
          f'{bad.state}[{bad.code}]')
    nums = [v['display_number'] for v in G.GATES.values()]
    check('  display numbers are unique, so an old return can still be read',
          len(nums) == len(set(nums)), str(sorted(nums)))
    check('  and every gate carries one', all(isinstance(n, int) for n in nums))


def test_B_undecided_blocks_exactly_as_no_does():
    print('\nB. LICENSING_CLEARANCE is UNDECIDED and that is not a pass')
    lic = G.GATES['LICENSING_CLEARANCE']
    check('it is UNDECIDED, not YES and not NO',
          lic['state'] == G.UNDECIDED, lic['state'])
    r = G.assert_scope_allowed(G.RESEARCH)
    check('  research is NOT blocked by it -- that is the declared scope',
          r.state is State.PASS
          and 'LICENSING_CLEARANCE' not in r.evidence['blocking_gates'],
          f'{r.state}[{r.code}] {r.evidence["blocking_gates"]}')
    for scope in (G.PRODUCTION, G.COMMERCIAL):
        p = G.assert_scope_allowed(scope)
        check(f'  {scope} IS blocked by it',
              p.state is State.FAIL
              and p.evidence['blocking_gates'].get('LICENSING_CLEARANCE')
              == G.UNDECIDED, str(p.evidence['blocking_gates']))


def test_C_ownership_gate_matches_the_audit():
    print('\nC. the gate state is not written independently of the evidence')
    o = OA.audit()
    check('the audit does not verify single ownership',
          o.evidence['single_adjustment_ownership_verified'] is False)
    check('  and the gate says NO, so the two agree',
          G.GATES['SINGLE_ADJUSTMENT_OWNERSHIP']['state'] == G.NO)
    check('  it blocks production and commercial, not research',
          G.GATES['SINGLE_ADJUSTMENT_OWNERSHIP']['blocks']
          == (G.PRODUCTION, G.COMMERCIAL))


def test_D_readiness_is_four_states_not_one():
    print('\nD. the composite is withdrawn')
    w = G.readiness('WEEK2_OAS1_FIT_READY_TO_EXECUTE')
    check('the old composite REFUSES rather than returning a value',
          w.state is State.FAIL and w.code == 'READINESS_STATE_WITHDRAWN',
          f'{w.state}[{w.code}]')
    check('  and says why', 'no fitting body' in w.detail, w.detail[:100])
    for name, want in (('WEEK2_OAS1_FIT_SPEC_READY', G.YES),
                       ('WEEK2_OAS1_PREFLIGHT_READY', G.YES),
                       ('WEEK2_OAS1_FIT_EXECUTABLE', G.NO),
                       ('WEEK2_OAS1_DOWNSTREAM_LAWFUL', G.NO)):
        r = G.readiness(name)
        check(f'  {name} = {want}', r.state is State.PASS and r.value == want,
              f'{r.state} {getattr(r, "value", None)}')
    c = G.readiness('COLD_START_VALIDATION')
    check('  COLD_START_VALIDATION = NOT_EVALUATED, never PASS',
          c.value == G.NOT_EVALUATED, str(c.value))


def test_E_spec_and_preflight_ready_do_not_imply_executable():
    print('\nE. the distinction the false green collapsed')
    spec = G.readiness('WEEK2_OAS1_FIT_SPEC_READY').value
    pre = G.readiness('WEEK2_OAS1_PREFLIGHT_READY').value
    ex = G.readiness('WEEK2_OAS1_FIT_EXECUTABLE').value
    check('SPEC_READY and PREFLIGHT_READY are both YES',
          spec == G.YES and pre == G.YES)
    check('  while FIT_EXECUTABLE is NO, and no code derives one from the '
          'others', ex == G.NO)
    down = G.readiness('WEEK2_OAS1_DOWNSTREAM_LAWFUL').value
    check('  and DOWNSTREAM_LAWFUL is independent of all three', down == G.NO)


def test_F_research_fit_gate_set_is_derived_not_asserted():
    print('\nF. which gates a research fit must clear')
    derived = tuple(g for g, v in G.GATES.items() if G.RESEARCH in v['blocks'])
    check('the set is computed from the blocks field',
          G.RESEARCH_FIT_GATES == derived, str(G.RESEARCH_FIT_GATES))
    check('  it does NOT include SINGLE_ADJUSTMENT_OWNERSHIP',
          'SINGLE_ADJUSTMENT_OWNERSHIP' not in G.RESEARCH_FIT_GATES)
    check('  nor CURRENT_SEASON_FRESHNESS, which is about live boards',
          'CURRENT_SEASON_FRESHNESS' not in G.RESEARCH_FIT_GATES)
    check('  nor LICENSING_CLEARANCE',
          'LICENSING_CLEARANCE' not in G.RESEARCH_FIT_GATES)
    check('  and every gate in it is YES',
          all(G.GATES[g]['state'] == G.YES for g in G.RESEARCH_FIT_GATES),
          str({g: G.GATES[g]['state'] for g in G.RESEARCH_FIT_GATES}))


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in (test_A_identity_is_the_name,
               test_B_undecided_blocks_exactly_as_no_does,
               test_C_ownership_gate_matches_the_audit,
               test_D_readiness_is_four_states_not_one,
               test_E_spec_and_preflight_ready_do_not_imply_executable,
               test_F_research_fit_gate_set_is_derived_not_asserted):
        fn()
    for n in NOT_EXECUTED:
        print(f'  NOT_EXECUTED {n}')
    print(f'\n{PASSED} passed, {FAILED} failed, {len(NOT_EXECUTED)} NOT_EXECUTED')
    raise SystemExit(1 if FAILED else 0)
