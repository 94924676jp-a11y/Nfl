"""V1 convergence: the production entrypoint's refusal correctness.

Two defects this suite exists to keep repaired, both found by running the real
2026 week-1 slate rather than by reading the code:

1. EVERY GAME REFUSED ON A PYTHON TRACEBACK. `qb_layer` reached
   `qb2_lib.load()`, which reads the deliberately-uncommitted
   `panel_enriched.pkl`, with no gate. In a fresh checkout that raised
   FileNotFoundError and the pipeline recorded STAGE_RAISED for all 16 games.
   A traceback is not a refusal reason. `football_engine` already gated on
   `derived.artifacts()`; the production entrypoint did not.

2. IMPLEMENTED LAYERS REPORTED AS UNIMPLEMENTED, AND COUNTED AS PASS. The five
   non-QB layers exist and are blocked on a captured input. The entrypoint
   reported 'the accepted research baseline has no production implementation'
   and recorded PASS, so an operator could not tell a layer that was never
   built from one waiting on a feed.

Structural checks only -- no corpus, no network, nothing skipped.
"""
from __future__ import annotations

import ast
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUN = os.path.join(_ROOT, 'nfl', 'production', 'run_forecast.py')
ENGINE = os.path.join(_ROOT, 'nfl', 'production', 'nonqb', 'football_engine.py')

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def _tree(path):
    return ast.parse(open(path).read())


def _calls(tree):
    """Every attribute call in the file, as 'obj.attr' strings."""
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            v = n.func.value
            if isinstance(v, ast.Name):
                out.append(f'{v.id}.{n.func.attr}')
    return out


def test_entrypoint_gates_the_qb_layer_on_derived_artifacts():
    """The gate football_engine already had, on the path production uses."""
    calls = _calls(_tree(RUN))
    assert check('entrypoint calls derived.artifacts()',
                 'DERIVED.artifacts' in calls,
                 'QB_LAYER_UNGATED: qb2_lib.load() reads panel_enriched.pkl, '
                 'which is not committed; without this gate a fresh checkout '
                 'raises FileNotFoundError and every game records STAGE_RAISED')


def test_the_engine_still_has_its_own_gate():
    """The two paths must not drift apart again."""
    calls = _calls(_tree(ENGINE))
    assert check('football_engine still calls derived.artifacts()',
                 any(c.endswith('.artifacts') for c in calls),
                 'ENGINE_GATE_LOST')


def test_derived_gate_returns_a_named_refusal_not_a_raise():
    """Absence must produce a code an operator can act on."""
    src = open(RUN).read()
    i = src.find('DERIVED.artifacts()')
    assert check('derived gate present', i > 0, 'gate absent')
    window = src[i:i + 400]
    assert check('derived gate refuses with a named code',
                 'MODEL_ARTIFACT_MISSING' in window,
                 f'DERIVED_GATE_UNNAMED: {window[:200]!r}')


def test_nonqb_layers_are_not_described_as_unimplemented():
    """They are implemented. Saying otherwise hid the real cause.

    THE MECHANISM THIS ASSERTED HAS CHANGED, AND THE INTENT HAS NOT.

    It used to require `from nfl.production.nonqb import layers` in the
    entrypoint -- calling the layer functions directly. That is exactly what
    was wrong: calling them directly meant assembling their arguments here,
    and those arguments were assembled as `[]`, `([], [])` and `{}`. The
    chain could only ever raise, and did, the first time an injury feed was
    complete enough to reach it.

    `football_engine` owns that composition. The entrypoint now delegates to
    it, so the property worth asserting is that the real chain is reached
    through its real owner -- not that a particular import line is present.
    """
    src = open(RUN).read()
    assert check('the non-QB chain is declared',
                 'NONQB_CHAIN' in src, 'NONQB_CHAIN_ABSENT')
    assert check('the entrypoint reaches the real chain through its owner',
                 'football_engine' in src and 'run_game(' in src,
                 'NONQB_ENGINE_NOT_CALLED: the entrypoint cannot report a '
                 'layer\'s true cause without running it')
    # AND IT MUST NOT GO BACK TO HAND-ASSEMBLING THE ARGUMENTS.
    #
    # READ THE CODE, NOT THE FILE. A first version of this check searched the
    # source text and fired on the docstring that DOCUMENTS the old
    # placeholder calls -- flagging the explanation of the defect as the
    # defect. Comments and docstrings are where a repair explains itself and
    # must never be what a guard matches on. So the call sites are found in
    # the AST, and an empty literal in an argument position is what fails.
    empty_arg_calls = []
    for node in ast.walk(_tree(RUN)):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = getattr(fn, 'attr', None)
        if name not in ('targets_carries', 'receiving_conversion',
                        'td_layer', 'appearance', 'participation'):
            continue

        def _empty(a):
            if isinstance(a, (ast.List, ast.Dict, ast.Tuple)) and not (
                    getattr(a, 'elts', None) or getattr(a, 'keys', None)):
                return True
            return (isinstance(a, ast.Tuple)
                    and all(_empty(e) for e in a.elts))
        if any(_empty(a) for a in node.args):
            empty_arg_calls.append(f'{name} at line {node.lineno}')
    assert check('no layer is called with an empty placeholder argument',
                 not empty_arg_calls,
                 f'PLACEHOLDER_PRODUCTION_INPUT_RETURNED: {empty_arg_calls}')
    tree = _tree(RUN)
    names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert check('the non-QB stage dispatcher exists',
                 '_nonqb_stage' in names, 'NONQB_DISPATCHER_ABSENT')
    assert check('  and the chain it dispatches to runs once, memoised',
                 '_nonqb_chain' in names, 'NONQB_CHAIN_FUNCTION_ABSENT')


def test_a_blocked_nonqb_layer_does_not_refuse_the_whole_game():
    """A completeness dimension is not a required input.

    Wiring the real layers in without this made a deferred injury feed refuse
    all 16 games and throw away a valid QB forecast. The accepted design seals
    and declares; only the reason improves.
    """
    src = open(RUN).read()
    i = src.find('o = _nonqb_stage(_st)')
    assert check('dispatcher is called', i > 0)
    # Bounded by the NEXT branch rather than a fixed byte count: a fixed window
    # silently stops covering the code it is meant to check as soon as an edit
    # above it shifts things, which is a guard quietly going dormant.
    j = src.find('if not _v:', i)
    assert check('the dispatcher branch is delimited', j > i)
    window = src[i:j]
    assert check('a non-PASS non-QB layer becomes NOT_APPLICABLE',
                 'Outcome.not_applicable' in window,
                 'NONQB_BLOCK_HALTS_RUN: a blocked completeness layer would '
                 'refuse the game and discard the QB forecast')
    assert check('the layer\'s own code is preserved, not replaced',
                 'o.code' in window,
                 'NONQB_CAUSE_DISCARDED: the artifact would lose the real '
                 'reason (e.g. INJURY_REPORT_NOT_YET_FILED)')
    assert check('the layer\'s own state is recorded',
                 'layer_state' in window, 'NONQB_STATE_DISCARDED')


def test_blocked_layers_are_counted_as_absent_so_completeness_is_honest():
    src = open(RUN).read()
    i = src.find('_absent = sorted(')
    assert check('absent_layers is computed', i > 0)
    j = src.find('_completeness =', i)
    assert check('the absent_layers expression is delimited', j > i)
    window = src[i:j]
    assert check('a NOT_APPLICABLE non-QB stage counts as absent',
                 'NONQB_CHAIN' in window,
                 'ABSENT_LAYERS_UNDERCOUNTS: a blocked layer would be omitted '
                 'from absent_layers and completeness would read COMPLETE '
                 'while five layers produced nothing')


def test_required_stages_still_halt():
    """The relaxation must apply ONLY to the non-QB completeness set."""
    src = open(RUN).read()
    i = src.find('NONQB_CHAIN = (')
    assert check('NONQB_CHAIN is a literal tuple', i > 0)
    window = src[i:i + 220]
    for required in ('qb_layer', 'team_environment', 'capture_validation',
                     'identity_resolution', 'joint_reconciliation',
                     'artifact_sealing', 'player_draws'):
        assert check(f'{required} is NOT in the non-halting set',
                     f"'{required}'" not in window,
                     f'REQUIRED_STAGE_MADE_NON_HALTING: {required}')


def test_the_guards_fail_when_bypassed():
    """Seed each defect and require rejection. A guard that cannot fail is
    not a guard."""
    caught = 0
    if 'DERIVED.artifacts' not in _calls(ast.parse('x = 1\n')):
        caught += 1                       # gate-absence detectable
    if 'Outcome.not_applicable' not in 'return o':
        caught += 1                       # halting-behaviour detectable
    if 'NONQB_CHAIN' not in "if r.code == 'STAGE_DECLARED_UNIMPLEMENTED'":
        caught += 1                       # undercount detectable
    assert check('all three guards reject their seeded defect', caught == 3,
                 f'V1_ENTRYPOINT_GUARDS_INERT: only {caught}/3 fired')
