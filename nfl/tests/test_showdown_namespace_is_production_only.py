"""`nfl/dfs/showdown/` holds production capability only. Nothing else.

Until 2026-09-25 it held 21 modules: one genuine production module and three
different historical slates' one-off scripts (DET/BUF, IND@KC, NYG@LAR). The
location asserted that all 21 were one generic DraftKings Showdown library.
They were not, and five of them could not even be imported.

The moves are cheap to make and cheap to undo. What is expensive is the
namespace silently refilling, which is what happened the first time -- nobody
decided to put three slates in a production package, it just accreted. So the
membership is asserted here rather than left to notice.

A NEW MODULE ADDED HERE FAILS THIS SUITE. That is the point. Adding it to
PRODUCTION below is a deliberate act that says: this is generic capability,
reachable from production, not a script for one game.
"""
import ast
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

SHOWDOWN = _REPO / 'nfl/dfs/showdown'

#: Reusable production capability. Classified 2026-09-25 by importer map and
#: fixture-pin scope; see nfl/research/findings/SHOWDOWN_NAMESPACE_CLASSIFICATION.md
PRODUCTION = {
    'universe',            # 16 importers, incl. 3 postgame graders + dual_board
    'kicker_identity',     # imported by universe
    'universe_contract',
    'candidates',
    'portfolio_report',
    'captain_metrics',
    'correlation',
    'scenarios',
    'optimal_worlds',
}

#: The two modules whose fixture pin is at MODULE level, so it binds every
#: caller. The rest pin only inside main(), which is a CLI output path.
#: Remove a name here ONLY when the pin is gone, never to make this pass.
PINNED_AT_MODULE_LEVEL = {'universe', 'kicker_identity'}

MOVED = {
    'nfl/research/dfs/IND_KC': ('build_showdown', 'dk_universe_showdown',
                                'eval_props_indkc', 'write_props_md',
                                'write_showdown_md'),
    'nfl/research/showdown_fixture/code': (
        'cleanup_pool', 'select_no_tracy', 'select_scale_invariant',
        'resolve_inactives', 'run_research_fixture', 'research_fixture',
        'build_gpp20'),
}

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


def _modules(d):
    return {p.stem for p in Path(d).glob('*.py') if p.stem != '__init__'}


def test_the_namespace_holds_exactly_the_production_set():
    print('\n[1] membership is asserted, not noticed')
    here = _modules(SHOWDOWN)
    extra = sorted(here - PRODUCTION)
    check('no module here is unclassified', not extra,
          f'unclassified: {extra} -- classify it and add it to PRODUCTION, or '
          f'move it to research' if extra else f'{len(here)} modules')
    gone = sorted(PRODUCTION - here)
    check('every classified module is still here', not gone, str(gone))


def test_no_slate_research_came_back():
    print('\n[2] the three slates stayed moved')
    for d, mods in MOVED.items():
        there = _modules(_REPO / d)
        missing = sorted(set(mods) - there)
        check(f'{d} still holds its {len(mods)}', not missing, str(missing))
        back = sorted(set(mods) & _modules(SHOWDOWN))
        check(f'...and none of them is back in nfl/dfs/showdown', not back,
              str(back))


def test_a_production_module_may_not_pin_a_slate_at_module_level():
    print('\n[3] module-level pins bind every caller; main() pins do not')
    found = {}
    for p in sorted(SHOWDOWN.glob('*.py')):
        src = p.read_text()
        pins = [i + 1 for i, ln in enumerate(src.splitlines())
                if 'DET_BUF' in ln or '2026W2' in ln or '2026_02' in ln]
        if not pins:
            continue
        # Resolve each pin's enclosing scope from the AST rather than guessing
        # from line order: a line AFTER `if __name__` can still be inside a
        # function defined above it, and a line before it can be at module
        # level. Reading line numbers instead of the tree got this backwards
        # the first time it was measured.
        tree = ast.parse(src)
        scope = {}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for ln in range(node.lineno,
                                (node.end_lineno or node.lineno) + 1):
                    scope.setdefault(ln, node.name)
        if any(ln not in scope for ln in pins):
            found[p.stem] = [ln for ln in pins if ln not in scope]
    check('only the two known modules pin at module level',
          set(found) == PINNED_AT_MODULE_LEVEL,
          f'{sorted(found)} vs expected {sorted(PINNED_AT_MODULE_LEVEL)}')
    for m in sorted(set(found) - PINNED_AT_MODULE_LEVEL):
        check(f'{m} has acquired a module-level slate pin', False,
              f'lines {found[m]} -- a pin here binds every caller')


def test_the_production_set_imports_cleanly():
    print('\n[4] a production module imports without doing its work')
    import importlib
    for m in sorted(PRODUCTION):
        try:
            importlib.import_module(f'nfl.dfs.showdown.{m}')
            check(f'{m} imports clean', True)
        except Exception as e:                                   # noqa: BLE001
            check(f'{m} imports clean', False, f'{type(e).__name__}: {e}')


def main():
    print(__doc__.strip().splitlines()[0])
    test_the_namespace_holds_exactly_the_production_set()
    test_no_slate_research_came_back()
    test_a_production_module_may_not_pin_a_slate_at_module_level()
    test_the_production_set_imports_cleanly()
    print(f'\n{PASSED} passed, {FAILED} failed')
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())
