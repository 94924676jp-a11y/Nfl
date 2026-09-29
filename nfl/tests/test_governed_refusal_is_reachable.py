#!/usr/bin/env python3.12
"""A refusal that raises NameError is not a refusal.

THE DEFECT THIS EXISTS TO PREVENT, found 2026-09-29. `nfl/tools/search_quality_gate.py` built two
BLOCKED outcomes with `cause=Cause.DEPENDENCY` and never imported `Cause`. Both lines are on refusal
paths, and neither fires unless the benchmark projection load is itself refused -- which only happens
once a proprietary module is imported in the same interpreter. So the module imported cleanly, passed
every test in a fresh process, and raised `NameError: name 'Cause' is not defined` the moment it had
to refuse. A governed refusal is the one path that must never crash, because it is what runs when
something has already gone wrong.

WHY AN AST CHECK RATHER THAN IMPORTING EVERYTHING. The name resolves at call time, not import time,
so importing the module proves nothing; and calling every refusal path in every module is not
possible. Reading the source and asking "is this name bound anywhere in this module" is exact for
this defect class and costs nothing.

SCOPE. The governance vocabulary only -- Cause, State, Outcome, OutcomeError. An unbound name
anywhere else is a linter's business; an unbound one HERE means a refusal cannot be constructed.
"""
from __future__ import annotations

import ast
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tests import _registry  # noqa: E402

#: The refusal primitives. Using one without binding it means the refusal path raises instead.
GOVERNANCE_NAMES = ('Cause', 'State', 'Outcome', 'OutcomeError')

#: Where the primitives are DEFINED, so the definition site is not reported as a user of them.
DEFINITION_SITE = 'sportsplatform/governance/outcome.py'

RESULTS = []


def check(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


def _bound_names(tree) -> set:
    """Every name bound at any level: imports, defs, classes, assignments, args, comprehensions."""
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom):
            out |= {(a.asname or a.name) for a in n.names}
        elif isinstance(n, ast.Import):
            out |= {(a.asname or a.name.split('.')[0]) for a in n.names}
        elif isinstance(n, ast.ClassDef):
            out.add(n.name)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.add(n.name)
            for a in (list(n.args.args) + list(n.args.kwonlyargs) + list(n.args.posonlyargs)
                      + [x for x in (n.args.vararg, n.args.kwarg) if x]):
                out.add(a.arg)
        elif isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            out.add(n.id)
        elif isinstance(n, ast.Global):
            out |= set(n.names)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            out.add(n.name)
    return out


def _annotation_name_nodes(tree) -> set:
    """Name nodes sitting in an annotation position.

    EXCLUDED FROM THE SCAN, and the reason matters. Under `from __future__ import annotations` every
    annotation is stored as a string and never evaluated, so `def f() -> Outcome:` in a module that
    does not import Outcome does NOT raise -- it is a type-checker concern, not the crashing-refusal
    defect this guard is named for. run_audit.py had exactly that and was the guard's first false
    positive. A guard that reports two different defects under one name teaches people to ignore it.
    """
    out = set()
    for n in ast.walk(tree):
        subs = []
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            subs = [n.returns] + [a.annotation for a in
                                  (list(n.args.args) + list(n.args.kwonlyargs)
                                   + list(n.args.posonlyargs))]
        elif isinstance(n, ast.AnnAssign):
            subs = [n.annotation]
        for sub in subs:
            if sub is None:
                continue
            for m in ast.walk(sub):
                if isinstance(m, ast.Name):
                    out.add(id(m))
    return out


def unbound_governance_names():
    """Every module using a bare governance name it never binds, with line numbers."""
    bad = []
    for f in sorted(_REPO.rglob('*.py')):
        rel = str(f.relative_to(_REPO))
        if '/.git/' in rel or '__pycache__' in rel or rel == DEFINITION_SITE:
            continue
        try:
            tree = ast.parse(f.read_text())
        except (SyntaxError, UnicodeDecodeError):
            continue
        bound = _bound_names(tree)
        ann = _annotation_name_nodes(tree)
        for want in GOVERNANCE_NAMES:
            if want in bound:
                continue
            lines = sorted({n.lineno for n in ast.walk(tree)
                            if isinstance(n, ast.Name) and n.id == want
                            and isinstance(n.ctx, ast.Load) and id(n) not in ann})
            if lines:
                bad.append({'module': rel, 'name': want, 'lines': lines})
    return bad


@check('no module uses a governance primitive it never binds')
def t_no_unbound():
    bad = unbound_governance_names()
    assert not bad, (
        'these modules reference a refusal primitive they never import, so the refusal path raises '
        'NameError instead of returning an Outcome:\n  '
        + '\n  '.join(f"{b['module']} uses bare {b['name']} at {b['lines']}" for b in bad))
    return 'every bare Cause/State/Outcome/OutcomeError use is bound in its own module'


@check('LOAD-BEARING: the check finds a planted unbound primitive')
def t_finds_a_plant():
    import tempfile
    d = pathlib.Path(tempfile.mkdtemp(dir=str(_REPO)))
    try:
        (d / 'planted.py').write_text(
            'def f():\n    return Outcome.blocked("X", "y", cause=Cause.DATA)\n')
        bad = unbound_governance_names()
        found = {b['name'] for b in bad if b['module'].startswith(d.name)}
        assert found == {'Outcome', 'Cause'}, (
            f'the scan missed a planted unbound primitive; found {found}. A guard that cannot find '
            f'the defect it is named for is not a guard.')
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)
    return 'a planted module using bare Outcome and Cause is detected by name and line'


@check('an import under a different alias is NOT reported')
def t_no_false_positive():
    import tempfile
    d = pathlib.Path(tempfile.mkdtemp(dir=str(_REPO)))
    try:
        (d / 'ok.py').write_text(
            'from sportsplatform.governance.outcome import Cause, Outcome\n'
            'def f():\n    return Outcome.blocked("X", "y", cause=Cause.DATA)\n')
        (d / 'ok2.py').write_text(
            'from sportsplatform.governance import outcome as O\n'
            'def f():\n    return O.Outcome.blocked("X", "y", cause=O.Cause.DATA)\n')
        bad = [b for b in unbound_governance_names() if b['module'].startswith(d.name)]
        assert not bad, (
            f'a correctly-importing module was reported: {bad}. A guard that cries wolf gets '
            f'switched off, and then it guards nothing.')
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)
    return 'a direct import and a module-qualified use are both accepted'


_EMITTED = _registry.emit(globals(), RESULTS)


def test_zz_every_check_passed():
    # The tally tripwire, in this module's own source because run_suite recognises it by shape.
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


def main() -> int:
    for fname in _EMITTED:
        try:
            globals()[fname]()
        except Exception:  # noqa: BLE001  -- already printed and counted by the wrapper
            pass
    print(f'\n{PASSED} passed, {FAILED} failed, {len(RESULTS)} checks')
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())
