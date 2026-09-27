"""One accessor for the Outcome value, and the ad-hoc idiom stays gone.

THE ASYMMETRY, WHICH IS REAL AND IS NOT FIXED HERE

`Outcome.ok(code, value, ...)` has `value` as a real parameter. `Outcome.fail`,
`.blocked`, `.deferred` and `.not_applicable` are `(code, detail, **evidence)` --
no `value` parameter -- so `value={...}` on those does not set `.value`; it
silently becomes `evidence['value']`. Measured at HEAD: **78 call sites across
28 files** pass `value=` to a non-ok constructor. Every one of those authors
wrote it expecting `.value`.

`gate.payload(outcome)` is the project's answer, and its own docstring says
"this project has now written that bug twice. One accessor."

WHAT THIS FILE GUARDS (DEF-084)

Not the asymmetry -- that is declared debt, because changing the governance type
every layer depends on has a 78-site blast radius and belongs in its own change.

What it guards is that the accessor is REACHED. Correct code that is not reached
is inert, and at the time this was written the census read 7 canonical calls
against 8 ad-hoc `x.value or x.evidence.get('value')` sites -- two of them inside
`gate.py` itself, sixty lines above the accessor it defines, and one in
`run_board.py` four lines from a correct `GATE.payload(gt)` call.

WHY THE AD-HOC IDIOM IS WRONG AND NOT MERELY UGLIER

`x.value or x.evidence.get('value')` uses `or`, so a `.value` that is
legitimately falsy -- `{}`, `0`, `[]`, an empty result set -- is treated as
absent and the read falls through to evidence. That is this project's recurring
defect class: falsy is not missing. It is the same shape as DEF-076, where the
string `'NONE'` tested truthy and a census of proofs read as complete.
`payload()` type-checks instead, so it does not have the bug.

`run_board.py` had the sharpest form, `a.value or a.evidence['value']` with no
`.get`: a falsy `.value` on an outcome carrying no `value` key raised KeyError
rather than reporting the refusal. A refusal is a valid result; a crash is a
defect.
"""
from __future__ import annotations

import ast
import os
import pathlib
import re
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.production.review.gate import payload                  # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome    # noqa: E402

PASSED = FAILED = 0
REPO = pathlib.Path(_ROOT)
#: `x.value or ...evidence[...'value'...]` in any spacing.
ADHOC = re.compile(r"\.value\s+or\s+[^\n]*evidence(\.get\(|\[)['\"]value['\"]")


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def _py_files():
    for p in sorted(REPO.rglob('*.py')):
        s = str(p)
        if '/__pycache__/' in s or '/.git/' in s:
            continue
        yield p


# ============================================ the accessor's own behaviour

def test_it_finds_the_value_on_a_passing_outcome():
    check('ok(value=dict) is returned', payload(Outcome.ok('C', {'a': 1}))
          == {'a': 1})


def test_it_finds_the_value_on_a_failing_outcome():
    o = Outcome.fail('C', 'd', value={'a': 1})
    check('.value is None on a failed outcome', o.value is None, repr(o.value))
    check('but payload still finds it', payload(o) == {'a': 1}, str(payload(o)))


def test_an_empty_dict_value_is_returned_as_an_empty_dict():
    """The property the `or` idiom got wrong."""
    check('ok(value={}) gives {}', payload(Outcome.ok('C', {})) == {})
    f = Outcome.fail('C', 'd', value={})
    check('fail(value={}) gives {} rather than falling through',
          payload(f) == {}, str(payload(f)))


def test_a_missing_value_is_an_empty_dict_not_a_crash():
    check('fail with no value does not raise',
          payload(Outcome.fail('C', 'd')) == {})
    # `blocked` additionally requires a keyword-only `cause`, which is right:
    # a blockage without a stated cause is the thing this project refuses.
    check('blocked with no value does not raise',
          payload(Outcome.blocked('C', 'd', cause=Cause.DATA)) == {})


def test_a_non_dict_value_is_not_returned_as_one():
    """Callers do `.get(...)` on the result, so it must always be a dict."""
    for v in ([1, 2], 'text', 7, None):
        check(f'a {type(v).__name__} value yields a dict',
              isinstance(payload(Outcome.ok('C', v)), dict),
              repr(payload(Outcome.ok('C', v))))


def test_it_tolerates_something_that_is_not_an_outcome():
    check('None does not raise', payload(None) == {})
    check('an object without the fields does not raise',
          payload(object()) == {})


# ==================================== the adoption ratchet (the real guard)

def test_the_adhoc_idiom_is_absent_from_production():
    offenders = []
    for p in _py_files():
        if '/tests/' in str(p):
            continue
        for i, line in enumerate(p.read_text().splitlines(), 1):
            if ADHOC.search(line):
                offenders.append(f'{p.relative_to(REPO)}:{i}')
    check('no production module reads the value with the ad-hoc `or` idiom',
          not offenders,
          f'{offenders} -- use gate.payload(outcome); see DEF-084')


def test_the_idiom_is_absent_across_two_lines_as_well():
    """It was split over two lines in gate.py, which a line scan would miss."""
    offenders = []
    for p in _py_files():
        if '/tests/' in str(p):
            continue
        if ADHOC.search(p.read_text()):
            offenders.append(str(p.relative_to(REPO)))
    check('not present across line breaks either', not offenders,
          str(offenders))


def test_the_accessor_is_actually_called():
    """A ratchet that passes because nothing reads the value proves nothing."""
    n = 0
    for p in _py_files():
        if '/tests/' in str(p):
            continue
        n += len(re.findall(r'\bpayload\(', p.read_text()))
    check('the canonical accessor has production callers', n >= 8, str(n))
    print(f'       payload( appears {n} times in production')


def test_the_producer_side_is_still_debt_and_is_counted():
    """Named debt beats a silent gap. If this number moves, say why."""
    n = 0
    for p in _py_files():
        try:
            tree = ast.parse(p.read_text())
        except Exception:                                      # noqa: BLE001
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            if not (isinstance(f, ast.Attribute)
                    and f.attr in ('fail', 'blocked', 'deferred',
                                   'not_applicable')):
                continue
            if getattr(f.value, 'id', None) not in ('Outcome', 'O'):
                continue
            if any(k.arg == 'value' for k in node.keywords):
                n += 1
    check('the producer-side count is in the band recorded with DEF-084',
          70 <= n <= 85,
          f'{n} sites pass value= to a non-ok Outcome constructor; DEF-084 '
          f'recorded 78. A large move means the asymmetry is being addressed '
          f'or spread, and either way the ledger entry needs updating.')
    print(f'       {n} producer sites still rely on the relocation')


if __name__ == '__main__':
    import traceback
    for _n in sorted(k for k in dict(globals()) if k.startswith('test_')):
        print(f'## {_n}')
        try:
            globals()[_n]()
        except Exception:                                      # noqa: BLE001
            FAILED += 1
            traceback.print_exc()
    print(f'\nPASSED {PASSED} FAILED {FAILED}')
    sys.exit(1 if FAILED else 0)
