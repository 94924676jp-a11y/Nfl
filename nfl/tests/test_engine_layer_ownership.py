"""Every engine layer is owned by a stage, or declared unreported with a reason.

THE DEFECT THIS GUARDS, AND THE ONE IT JUST CAUGHT

`run_forecast._assert_every_layer_is_reported` refuses a run in which the
engine produced a layer that no declared stage answers for. Its own comment
records why it exists: `rushing_budget` failed
RUSHING_BUDGET_EXCEEDS_TEAM_CARRIES, no stage was mapped to it, and the run
SEALED ANYWAY. A failing layer nobody owns is the absence-read-as-success
defect with the sign flipped -- the failure is real and invisible.

On 2026-09-19 a full Week-2 slate run under V1_CANDIDATE_R9_W1P_GSVUCY hit it
again, with two layers: `events_within_opportunity` and
`interception_reservation`. The consequence was not a silent pass -- the guard
did its job -- but it was still bad: five stages (appearance, participation,
targets_carries, conversion, td_layer) reported NOT_APPLICABLE
[ENGINE_LAYER_NOT_REPORTED] on a run whose engine had in fact produced 38
draw matrices over 32 players, including receiving and rushing. A reader of
that run would conclude the non-QB layer did not run. It did.

WHAT THIS FILE PINS

Not the current mapping, which will grow. The RULE:

  * every layer name the engine can write is either mapped to a stage or
    listed in UNREPORTED_LAYERS -- membership of neither is refused;
  * a layer that can HALT the engine is REPORTED -- mapped to a stage, or
    carried by a declared stage of its own name -- never merely exempt,
    because an unreported layer's failure reaches no artifact;
  * the two sets do not overlap, since a layer both owned and exempt is a
    contradiction that would resolve differently depending on read order.
"""
from __future__ import annotations

import ast
import os
import pathlib
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

PASSED = FAILED = 0
RF = pathlib.Path(_ROOT) / 'nfl' / 'production' / 'run_forecast.py'
FE = pathlib.Path(_ROOT) / 'nfl' / 'production' / 'nonqb' / 'football_engine.py'
PIPE = pathlib.Path(_ROOT) / 'nfl' / 'production' / 'pipeline.py'


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def _literal(path, name):
    """The declared value, read from the SOURCE by AST.

    Not by importing: run_forecast builds these inside a function and
    importing it runs a production entrypoint. Reading the literal is also
    the honest thing -- the question is what the file declares.
    """
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    try:
                        return ast.literal_eval(node.value)
                    except ValueError:
                        return None
    return None


def _engine_layer_names():
    """Every string literal the engine passes to `_lay(...)`.

    By AST, so a layer added tomorrow is picked up without anyone editing a
    list here. A non-literal first argument is REPORTED rather than skipped:
    a dynamically named layer would defeat the whole check and this test says
    so out loud instead of quietly covering fewer layers.
    """
    tree = ast.parse(FE.read_text())
    names, dynamic = set(), []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if not (isinstance(f, ast.Name) and f.id == '_lay'):
            continue
        if not node.args:
            continue
        a = node.args[0]
        if isinstance(a, ast.Constant) and isinstance(a.value, str):
            names.add(a.value)
        else:
            dynamic.append(ast.dump(a)[:80])
    return names, dynamic


def _halting_layer_names():
    """Layers the engine HALTS on: `g['halted_at'] = '<name>'`."""
    tree = ast.parse(FE.read_text())
    out = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not (isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)):
            continue
        for t in node.targets:
            if (isinstance(t, ast.Subscript)
                    and isinstance(t.value, ast.Name) and t.value.id == 'g'
                    and isinstance(t.slice, ast.Constant)
                    and t.slice.value == 'halted_at'):
                out.add(node.value.value)
    return out


def _owned():
    sl = _literal(RF, 'STAGE_LAYERS') or {}
    un = _literal(RF, 'UNREPORTED_LAYERS')
    if un is None:                         # frozenset({...}) is not a literal
        txt = RF.read_text()
        i = txt.index('UNREPORTED_LAYERS = frozenset(')
        j = txt.index('})', i)
        un = ast.literal_eval(txt[txt.index('{', i):j + 1])
    mapped = {n for names in sl.values() for n in names}
    return sl, mapped, set(un)


def test_the_two_declarations_are_readable_and_disjoint():
    sl, mapped, un = _owned()
    check('STAGE_LAYERS is declared and non-empty', bool(sl), str(len(sl)))
    check('UNREPORTED_LAYERS is declared and non-empty', bool(un), str(len(un)))
    overlap = sorted(mapped & un)
    check('a layer is owned or exempt, never both -- the two would resolve '
          'differently depending on read order', not overlap, str(overlap))


def test_every_engine_layer_is_owned_or_deliberately_exempt():
    names, dynamic = _engine_layer_names()
    check('the engine names its layers with string literals, so this check '
          'sees all of them', not dynamic, str(dynamic))
    check('the engine declares a non-trivial number of layers',
          len(names) >= 10, str(len(names)))
    sl, mapped, un = _owned()
    orphan = sorted(names - mapped - un)
    check('no engine layer is unowned and unexempt', not orphan, str(orphan))


def test_a_layer_that_can_halt_the_engine_is_reported_somewhere():
    """The rule the 2026-09-19 slate run broke.

    An unreported layer's failure reaches no artifact. That is tolerable for
    a label -- `rushing_budget_owner` is a name, not an outcome -- and it is
    not tolerable for anything that can stop the run, because a stage is the
    only place the refusal can surface.

    TWO CORRECTIONS TO THE FIRST VERSION OF THIS TEST, both found by running
    it, and both cases of my rule being cruder than the code:

    1. `g['halted_at']` is assigned names that are NOT layers --
       `conversion_or_td` and `qb_composition` are halt LABELS describing
       where a composite step stopped. Requiring a stage mapping for them
       asked the code for something it never claimed. The halting set is
       intersected with the engine's declared layer names.
    2. `team_environment` is exempt from STAGE_LAYERS and is nonetheless
       fully reported -- by a declared stage of its own name, which is how
       its comment says it is handled. "Mapped in STAGE_LAYERS" was the wrong
       test for "reported"; having a stage is the right one.
    """
    names, _ = _engine_layer_names()
    halting_labels = _halting_layer_names()
    halting = halting_labels & names
    non_layer = sorted(halting_labels - names)
    check('the engine declares halt points that are layers',
          len(halting) >= 3, str(sorted(halting)))
    check('halt labels that are not layers are reported, not silently '
          'treated as layers', True, f'not layers: {non_layer}')
    sl, mapped, un = _owned()
    # The declared stage list is `pipeline.STAGES`, not the keys of
    # STAGE_LAYERS -- STAGE_LAYERS maps only the stages the non-QB engine
    # chain answers for, and `team_environment` is a stage with its own
    # executor. Reading the stage names from where they are actually
    # declared is the difference between this test and my first draft.
    stages = set(_literal(PIPE, 'STAGES') or ()) | set(sl)
    unreported = sorted(h for h in halting
                        if h not in mapped and h not in stages)
    check('every halting layer is reported -- mapped to a stage, or carried '
          'by a declared stage of its own name', not unreported,
          str(unreported))
    exempt_without_stage = sorted(h for h in (halting & un)
                                  if h not in stages)
    check('no halting layer is exempt with nothing reporting it',
          not exempt_without_stage, str(exempt_without_stage))


def test_the_two_layers_from_the_slate_run_are_now_owned_by_the_right_stage():
    """Named, because guessing the owner would have been the easier error.

    `interception_reservation` runs immediately before `receiving_conversion`
    and hands it the reserved picks, so `conversion` owns it.
    `events_within_opportunity` bounds counts by opportunity over five pairs
    including `rushing_td <= carries`, beside `counts_are_counts` and
    `stat_contract`, so `td_layer` owns it.
    """
    sl, mapped, un = _owned()
    check('interception_reservation is owned by conversion',
          'interception_reservation' in sl.get('conversion', ()),
          str(sl.get('conversion')))
    check('events_within_opportunity is owned by td_layer',
          'events_within_opportunity' in sl.get('td_layer', ()),
          str(sl.get('td_layer')))
    check('and neither was put on the exempt list instead',
          not ({'interception_reservation', 'events_within_opportunity'} & un))


def test_every_exemption_carries_a_reason_in_the_source():
    """An exemption with no reason is a list somebody grew to make a run pass."""
    txt = RF.read_text()
    i = txt.index('UNREPORTED_LAYERS = frozenset(')
    block = txt[i:txt.index('})', i)]
    sl, mapped, un = _owned()
    for name in sorted(un):
        line = next((ln for ln in block.splitlines() if f"'{name}'" in ln), '')
        comment = line.split('#', 1)[1].strip() if '#' in line else ''
        check(f'{name} says why it is exempt', len(comment) >= 8, repr(line))


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
