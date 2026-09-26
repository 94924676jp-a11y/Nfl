"""A required gate nothing produces is a permanent block with no author.

`nfl/production/verdict.py` declares 23 gates, 18 required for the `football`
scope, and `CLEARING` is `('PASS',)` alone. `assess()` counts a gate ABSENT
from its results dict as `NOT_EVALUATED` -- "a gate nobody ran is not a gate
that passed" -- which is exactly right and is why this matters:

    a required gate with no producer can never clear, so the scope can never
    clear, and the verdict reports that as a property of the MODEL.

Measured 2026-09-26. Eight of the 23 gates have no production producer at all,
three of them required for `football`. With every producible gate set to PASS,
`assess()` returns BLOCKED / PRODUCT_RESEARCH_ONLY; set the other three to PASS
and it returns PASS / PRODUCT_DEPLOYABLE. So the block is real, and its cause is
three unwired gates rather than anything measured about football.

TWO OF THE THREE ARE PLAUSIBLY DELIBERATE and are declared as such below --
real money is NOT ENABLED and no candidate is promoted, so a gate that can never
clear is the intended kill switch. Declaring them makes the intent auditable
instead of indistinguishable from an oversight.

THE THIRD IS NOT. `GAME_ACCOUNTING_COHERENCE` has its evidence COMPUTED and
DISCARDED: football_engine calls `assert_named_owner_containment` and stores the
Outcome at `g['accounting']['rush_named_owner_containment']`, and nothing maps it
onto the gate. That is DEF-065's shape one layer up -- a control that runs,
records its verdict in the artifact, and does not reach the thing that enforces
it. DEF-072.

This suite exists so that a NEW required gate cannot be declared without either a
producer or an explicit statement that it is meant never to clear.
"""
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production import verdict as V  # noqa: E402

PASSED = 0
FAILED = 0

#: gate -> why it is MEANT to have no producer. An entry here is a claim that
#: the gate is a deliberate permanent block, not an oversight.
INTENTIONAL_PERMANENT_BLOCK = {
    'REAL_MONEY_SCOPE_AUTHORIZED':
        'real_money.status is NOT ENABLED and weekly_exposure_cap is UNSET with '
        'unset_is_blocking. A gate that cannot clear is the kill switch, and '
        'wiring a producer would be the defect.',
    'PROMOTION_STATUS_VALID_FOR_SCOPE':
        'no candidate is promoted, so no scope has a valid promotion status to '
        'report. Producing a PASS here would assert a promotion that has not '
        'happened.',
}

#: gate -> the defect tracking its missing wire.
PRODUCERLESS_AND_TRACKED = {
    'GAME_ACCOUNTING_COHERENCE': 'DEF-072',
}


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  PASS {label}' + (f' -- {detail}' if detail else ''))
    else:
        FAILED += 1
        print(f'  FAIL {label}' + (f' -- {detail}' if detail else ''))


def _producers(gate: str) -> list:
    """Non-test, non-research files naming this gate, excluding its declaration."""
    out = []
    for p in _REPO.rglob('*.py'):
        rel = str(p.relative_to(_REPO))
        if '__pycache__' in rel or '/tests/' in rel or rel.startswith('nfl/tests/'):
            continue
        if rel in ('nfl/production/verdict.py',):
            continue
        if rel.startswith(('nfl/research/', 'nfl/tools/')):
            continue
        try:
            if gate in p.read_text(errors='replace'):
                out.append(rel)
        except OSError:
            continue
    return out


def test_every_required_gate_is_produced_or_declared_unproducible():
    print('\n[1] no required gate is a permanent block by accident')
    req = V.required_gates('football')
    check('the football scope declares required gates', len(req) > 0, str(len(req)))
    undeclared = []
    for g in sorted(req):
        if _producers(g):
            continue
        if g in INTENTIONAL_PERMANENT_BLOCK or g in PRODUCERLESS_AND_TRACKED:
            continue
        undeclared.append(g)
    check('every producerless REQUIRED gate is declared or tracked',
          not undeclared,
          str(undeclared) or 'a new one here is a permanent block nobody '
                             'authored; declare it or wire it')


def test_the_declared_kill_switches_really_have_no_producer():
    print('\n[2] the declarations are true, not aspirational')
    for g, why in sorted(INTENTIONAL_PERMANENT_BLOCK.items()):
        prod = _producers(g)
        check(f'{g} still has no producer', not prod, str(prod) or why[:60])
    for g, deff in sorted(PRODUCERLESS_AND_TRACKED.items()):
        check(f'{g} is still unwired and tracked as {deff}',
              not _producers(g),
              'if a producer appears, close the defect and remove this entry')


def test_the_scope_cannot_clear_and_the_reason_is_the_gates():
    print('\n[3] the block is the gates, not a measurement about football')
    req = V.required_gates('football')
    blockers = set(INTENTIONAL_PERMANENT_BLOCK) | set(PRODUCERLESS_AND_TRACKED)
    best = {g: V.PASS for g in req if g not in blockers}
    o = V.assess(best, scope='football')
    check('with every producible gate PASSING the scope is still blocked',
          o.state.name != 'PASS', f'{o.state.name}[{o.code}]')
    allp = {g: V.PASS for g in req}
    o2 = V.assess(allp, scope='football')
    check('and it clears only once the unproduced gates are supplied',
          o2.state.name == 'PASS', f'{o2.state.name}[{o2.code}]')
    check('so PRODUCT_RESEARCH_ONLY here is a WIRING state, not a model verdict',
          o.code != o2.code,
          f'{o.code} vs {o2.code} -- a reader could reasonably take the first '
          f'as a statement about football')


def test_an_absent_gate_is_never_read_as_passing():
    print('\n[4] the property that makes all of this safe')
    check('CLEARING is PASS alone', V.CLEARING == ('PASS',), str(V.CLEARING))
    o = V.assess({}, scope='football')
    check('an empty results dict does NOT clear', o.state.name != 'PASS',
          f'{o.state.name}[{o.code}]')
    one = {g: V.PASS for g in V.required_gates('football')}
    missing = sorted(one)[0]
    del one[missing]
    o2 = V.assess(one, scope='football')
    check('dropping ONE required gate blocks the scope',
          o2.state.name != 'PASS', f'removed {missing} -> {o2.state.name}')


def main():
    print(__doc__.strip().splitlines()[0])
    test_every_required_gate_is_produced_or_declared_unproducible()
    test_the_declared_kill_switches_really_have_no_producer()
    test_the_scope_cannot_clear_and_the_reason_is_the_gates()
    test_an_absent_gate_is_never_read_as_passing()
    print(f'\n{PASSED} passed, {FAILED} failed')
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())
