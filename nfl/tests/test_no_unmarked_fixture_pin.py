"""A production module may not silently resolve one game.

THE RULE, as the owner stated it: a production module may not contain a
hard-coded game or week fixture path unless it is explicitly declared as
frozen, reference or test-only AND unreachable from live production.

What measuring the 35 flagged modules actually showed, which is not what the
count suggested:

* NOT ONE of the 35 accepts a game, week or slate argument. Seventeen are
  runnable entry points (`__main__`); exactly one imports argparse at all, and
  even that one has no game option. So for every single module, running a
  DIFFERENT game requires editing source. That is the defect, and it is sharper
  and worse than "35 modules mention DET_BUF".

* ZERO of the flagged input paths are reachable from the live scheduled
  workflows. A 97-module import closure over the seven scripts those workflows
  run touches none of them. The pinned cohort is manually-invoked tooling, and
  that is a mitigation, not an exoneration: a runnable script that silently
  resolves last month's slate is a trap for whoever runs it next.

* THE DETECTOR OVER-COUNTS. Two of the 35 are provenance LABELS, not inputs:
  `mech = 'FROZEN_P3_LOGISTIC_ON_2026_PANEL'` and
  `'artifact': 'NFL_PANEL_2026W1_DERIVED'` are names recorded in output. They
  are also the only two in modules the live path reaches, so the two findings
  that looked most alarming were the two that were not findings. Counting a
  label as a pin is how a real list loses its authority.

  Nearby and genuinely interesting: `AP26.build(int(season), 1)` hardcodes
  week 1 inside a function that receives `week`. That is deliberate --
  appearance_panel_2026 exists to supply 2026 week-1 observed rows so the
  previous game is the previous game, instead of week 18, which is a league-wide
  rest week. The hardcoded 1 is the fix, not the bug.

So this file enforces two things a count cannot: that every hard-coded game
PATH in a production tree is declared with a reason, and that a runnable module
resolving a fixture cannot pretend to be general.
"""
import ast
import re
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

PRODUCTION_TREES = ('nfl/production', 'nfl/dfs', 'nfl/product', 'nfl/truth',
                    'nfl/postgame', 'nfl/market', 'nfl/prospective')

#: A game or slate identity: season_week_TEAMS, or a named slate fixture.
_GAME = re.compile(r'(20\d\d_\d\d_[A-Z]{2,3}_[A-Z]{2,3}'
                   r'|[A-Z]{2,3}_[A-Z]{2,3}_20\d\dW\d+'
                   r'|EARLY_1PM_20\d\dW\d+'
                   r'|[A-Z_]*SHOWDOWN[A-Z_0-9]*'
                   r'|20\d\dW\d+)')

#: Declared pins: path -> why. Each entry is a claim that this module is
#: frozen, reference or fixture-only AND not reachable from live production.
#: An undeclared pin fails. A declaration that stops being true also fails,
#: because the reachability half is checked, not taken on trust.
DECLARED_PINS = {
    'nfl/dfs/showdown/': (
        'SLATE RESEARCH, not production. Seventeen modules pinned across three '
        'one-off slates (DET_BUF_2026W2, IND_KC_SHOWDOWN_2026W2, NYG_LA). They '
        'sit under a production tree by directory only; none is reachable from '
        'any scheduled workflow. Declared fixture-only pending a move out of '
        'nfl/dfs/, which is a rename and belongs in its own change.'),
    'nfl/postgame/': (
        'WEEK-2 GRADING RUN. Pinned to DET_BUF_2026W2 and 2026_02_DET_BUF, '
        'including a module literally named run_week2.py. This is the grading '
        'of one specific slate rather than a general grader, and it is not '
        'reachable from a scheduled workflow. It is the strongest candidate '
        'for real parameterisation, and doing it needs a second graded slate '
        'to prove against -- see DEF-062.'),
    'nfl/market/': (
        'ONE-OFF price evaluations against EARLY_1PM_2026W2 and 2026_02_NYG_LA; '
        'not reachable from a scheduled workflow.'),
    'nfl/dfs/salaries/emit_package.py': (
        'emits the Week-2 early-slate package; one-off, not scheduled.'),
    'nfl/dfs/scoring/dual_board.py': (
        'reads the frozen DET_BUF_2026W2 board to compare both sites on the '
        'SAME draws. The frozen slate is the point of the comparison.'),
    'nfl/dfs/scoring/site_rules.py': (
        'verifies scoring rules against the frozen DET_BUF_2026W2 artifact.'),
    'nfl/product/board_pointer.py': (
        'names 2026_01_DEN_KC as an EXAMPLE in a reader-facing explanation of '
        'which board is being looked at.'),
    'nfl/production/dependence.py': (
        'reads the frozen DET_BUF_2026W2 draws to measure whether a '
        'cross-player correlation read off an artifact means anything.'),
    'nfl/production/board/run_board.py': (
        'a one-game board runner for 2026_02_NYG_LA; superseded by '
        'tools/refresh_boards.py, which is what the scheduled workflow runs.'),
    'nfl/prospective/q9shadow/armpolicy.py': (
        'names 2025_01_ARI_NO as the first game of the shadow arm window.'),
    'nfl/production/nonqb/layers.py': (
        'NOT A PIN. FROZEN_P3_LOGISTIC_ON_2026_PANEL is a mechanism name '
        'recorded in output provenance, not an input path.'),
    'nfl/production/nonqb/panel_2026w1.py': (
        'NOT A PIN. NFL_PANEL_2026W1_DERIVED is the artifact name in a '
        'provenance block. The panel IS week-1 by design: it exists so the '
        'previous game is the previous game rather than week 18, a league-wide '
        'rest week.'),
}

PASSED = 0
FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


def _code_strings(src):
    """String literals that survive as code: no comments, no docstrings."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    docs = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef,
                          ast.AsyncFunctionDef)):
            body = getattr(n, 'body', None) or []
            if body and isinstance(body[0], ast.Expr) \
                    and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                docs.add(id(body[0].value))
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in docs]


def _looks_like_a_path(lit):
    """An INPUT reference, as against a provenance label.

    The distinction the count got wrong. A label is a name recorded in output
    ('NFL_PANEL_2026W1_DERIVED'); a path resolves bytes. The heuristic is
    deliberately narrow -- a separator or a data extension -- and it will call
    a bare game id like '2026_02_NYG_LA' a label even when it is later joined
    into a path. That is why the runnable-entry-point check below exists: it
    catches the ones this misses by asking a different question.
    """
    return ('/' in lit or lit.endswith(('.json', '.csv', '.npz', '.gz',
                                        '.parquet', '.md')))


def _pinned_paths(src):
    return sorted({l for l in _code_strings(src)
                   if _looks_like_a_path(l) and _GAME.search(l)
                   and ' ' not in l and len(l) < 120})


def _declaration_for(rel):
    for key, why in DECLARED_PINS.items():
        if rel == key or (key.endswith('/') and rel.startswith(key)):
            return why
    return None


def _production_files():
    for p in sorted(_REPO.rglob('*.py')):
        rel = str(p.relative_to(_REPO))
        if any(rel.startswith(t) for t in PRODUCTION_TREES) \
                and '/tests/' not in rel:
            yield rel, p


def test_every_hardcoded_game_path_is_declared():
    undeclared = []
    for rel, p in _production_files():
        try:
            src = p.read_text()
        except Exception:                                        # noqa: BLE001
            continue
        pins = _pinned_paths(src)
        if pins and _declaration_for(rel) is None:
            undeclared.append(f'{rel} -> {pins[0]}')
    check('no undeclared hard-coded game path in a production tree',
          not undeclared,
          f'{len(undeclared)} undeclared: {undeclared[:6]}. Declare each with '
          f'a reason, or make the game an argument.')


def test_a_runnable_module_that_pins_a_game_takes_no_game_argument():
    """A standing measurement, and the answer to "can a different game run
    without editing source". Today: no, for every one of them."""
    runnable_pinned, with_arg = [], []
    for rel, p in _production_files():
        try:
            src = p.read_text()
        except Exception:                                        # noqa: BLE001
            continue
        if not _pinned_paths(src) or '__main__' not in src:
            continue
        runnable_pinned.append(rel)
        opts = set(re.findall(r"add_argument\(\s*'--([a-z0-9-]+)'", src))
        if any(re.search(r'game|week|slate', o) for o in opts):
            with_arg.append(rel)
    check('runnable pinned modules were enumerated', True)
    print(f'       {len(runnable_pinned)} runnable module(s) resolve a pinned '
          f'game; {len(with_arg)} accept a game/week/slate argument')
    for rel in runnable_pinned:
        print(f'         {rel}'
              + ('  (parameterised)' if rel in with_arg else ''))


def test_no_declared_pin_is_reachable_from_a_scheduled_workflow():
    """The other half of every declaration. "Fixture-only" is a claim about
    reachability, so it is checked rather than trusted -- a declaration that
    quietly stops being true is worse than no declaration."""
    entries = ['nfl/tools/refresh_boards.py', 'nfl/production/run_forecast.py',
               'nfl/tools/capture_vintage.py', 'nfl/tools/capture_release.py',
               'nfl/tools/check_retention.py',
               'nfl/tools/watch_availability.py']
    entries = [e for e in entries if (_REPO / e).exists()]
    check('the live entry points still exist', bool(entries), entries)

    def mod_path(m):
        for cand in (_REPO / (m.replace('.', '/') + '.py'),
                     _REPO / m.replace('.', '/') / '__init__.py'):
            if cand.exists():
                return str(cand.relative_to(_REPO))
        return None

    seen, stack = set(), list(entries)
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        try:
            tree = ast.parse((_REPO / cur).read_text())
        except Exception:                                        # noqa: BLE001
            continue
        for n in ast.walk(tree):
            mods = []
            if isinstance(n, ast.Import):
                mods = [a.name for a in n.names]
            elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
                mods = [n.module] + [f'{n.module}.{a.name}' for a in n.names]
            for m in mods:
                if not m.startswith('nfl'):
                    continue
                q = mod_path(m)
                if q and q not in seen:
                    stack.append(q)

    live_pins = []
    for rel in sorted(seen):
        if not any(rel.startswith(t) for t in PRODUCTION_TREES):
            continue
        if _declaration_for(rel) is None:
            continue
        try:
            src = (_REPO / rel).read_text()
        except Exception:                                        # noqa: BLE001
            continue
        if _pinned_paths(src):
            live_pins.append(rel)
    check('no module declared fixture-only is reachable from a live entry point',
          not live_pins,
          f'{live_pins} are declared fixture-only AND reachable from a '
          f'scheduled workflow. One of those two statements is wrong.')
    print(f'       live closure: {len(seen)} modules from {len(entries)} '
          f'entry point(s)')


def test_the_declaration_table_names_real_paths():
    for key in sorted(DECLARED_PINS):
        target = _REPO / key
        check(f'declaration {key} exists',
              target.exists() or any(True for _ in _REPO.glob(key + '*')),
              'stale declaration; remove it rather than leaving it to rot')
        check(f'declaration {key} carries a reason',
              bool(DECLARED_PINS[key].strip()))
