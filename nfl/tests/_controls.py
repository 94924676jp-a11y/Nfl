"""OWNER RULE 2 (2026-10-02): a detector without a demonstrated trip case is not validated.

"Every detector, contradiction rule, invariance test, sanity check, and blocker must include at
least one positive control that is known to violate the rule and must be proven to trigger under
the authoritative runner."

WHAT THIS MODULE IS. The one place a test records that it drove a detector with a violating input
and observed the detector trip. Two ways to record, same row:

    from nfl.tests._controls import observe, positive_control

    @positive_control('nfl.tools.football_sanity:assess:QB_TARGETS_ABOVE_CEILING_WITHOUT_REASON')
    def test_qb_targets_trip():
        ...
        return o                      # the Outcome (or code string) the detector returned

    def test_something_else():
        o = FS.assess(bad_artifact)
        observe('nfl.tools.football_sanity:assess:QB_TARGETS_ABOVE_CEILING_WITHOUT_REASON', o)

A detector is named `<module>:<function>:<CODE>`. CODE is the Outcome code, the dict `state`, or
the refusal's class code the detector emits when it trips. `observe` compares what the detector
actually returned with CODE and records `tripped: true/false`; it never asserts, because the test's
own `check(...)` already does and a second assertion would hide which one fired.

WHERE THE RECORD GOES. Every observation is appended to the hits file (`NFL_CONTROL_HITS`, default
`nfl/tests/_control_hits.jsonl`, untracked) stamped with the runner's run id
(`NFL_SUITE_RUN_ID`, set by run_suite for itself and inherited by its own-process children). Like
the progress log it is append-only: a reader filters on run id. `run_suite` calls `validate()` at
the end of a run, writes `nfl/tests/DETECTOR_VALIDATION.json`, and FAILS the suite when a detector
in `DETECTORS.json` has no control that ran and tripped in that run.

THE MANIFEST. `nfl/tests/DETECTORS.json` lists the detectors the rule is enforced for today. It is
seeded from the inventory and grows by hand; `census()` compares it with every refusal code the
guard trees declare (via `nfl/tools/invariant_manifest.declared_refusals`) so a detector that is
not listed is REPORTED as unlisted, never silently ignored.
"""
from __future__ import annotations

import ast
import datetime as dt
import re as _re
import functools
import glob
import json
import os
import pathlib
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
TESTS = ROOT / 'nfl' / 'tests'
MANIFEST = TESTS / 'DETECTORS.json'
VALIDATION = TESTS / 'DETECTOR_VALIDATION.json'
HITS_DEFAULT = TESTS / '_control_hits.jsonl'

_DETECTOR_RE = _re.compile(r'^[a-z_][a-z0-9_.]*:[A-Za-z_][A-Za-z0-9_.]*:[A-Za-z][A-Za-z0-9_]+$')

VALIDATED = 'VALIDATED'
NO_CONTROL = 'UNVALIDATED_NO_CONTROL'
DID_NOT_TRIP = 'UNVALIDATED_CONTROL_DID_NOT_TRIP'
NOT_EXECUTED = 'UNVALIDATED_CONTROL_NOT_EXECUTED'
NOT_IN_RUN = 'NOT_IN_THIS_RUN'


def hits_path() -> pathlib.Path:
    return pathlib.Path(os.environ.get('NFL_CONTROL_HITS') or HITS_DEFAULT)


def run_id() -> str | None:
    return os.environ.get('NFL_SUITE_RUN_ID') or None


def _code_of(result) -> str | None:
    """The code a detector returned, whatever shape it returned it in."""
    if result is None:
        return None
    if isinstance(result, str):
        return result
    code = getattr(result, 'code', None)
    if isinstance(code, str):
        return code
    if isinstance(result, dict):
        for k in ('code', 'state', 'verdict', 'status'):
            v = result.get(k)
            if isinstance(v, str):
                return v
    return None


def _caller(depth: int) -> tuple[str, str]:
    import inspect
    fr = inspect.stack()[depth]
    mod = pathlib.Path(fr.filename)
    try:
        rel = str(mod.resolve().relative_to(ROOT))
    except ValueError:
        rel = mod.name
    return rel, fr.function


def observe(detector: str, result, *, _depth: int = 2) -> bool:
    """Record that `detector` was driven with a violating input and returned `result`.

    Returns whether it tripped (returned the manifest code). Never raises on the record itself:
    a control that cannot write its row still runs, and the missing row is what validate()
    reports as NOT_EXECUTED.
    """
    expected = detector.rsplit(':', 1)[-1]
    got = _code_of(result)
    tripped = got == expected
    module, function = _caller(_depth)
    row = {'run_id': run_id(), 'detector': detector, 'expected': expected, 'got': got,
           'tripped': bool(tripped), 'module': module, 'function': function,
           'pid': os.getpid(), 't': round(time.time(), 3)}
    try:
        with open(hits_path(), 'a') as fh:
            fh.write(json.dumps(row, sort_keys=True) + '\n')
    except OSError:
        pass
    return tripped


def positive_control(detector: str):
    """Decorate a test function that RETURNS what the detector returned."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapped(*a, **kw):
            r = fn(*a, **kw)
            observe(detector, r, _depth=2)
            return r
        wrapped.__positive_control__ = detector
        return wrapped
    return deco


# ------------------------------------------------------------------ static side
def load_manifest() -> list[dict]:
    doc = json.loads(MANIFEST.read_text())
    return list(doc['detectors'])


def declared_controls(test_glob: str = 'nfl/tests/test_*.py') -> dict[str, list[dict]]:
    """Every control declared in the test tree, by detector, found by AST (no import needed).

    Recognises `@positive_control('<detector>')` on a function and `observe('<detector>', ...)`
    calls with a constant first argument.
    """
    out: dict[str, list[dict]] = {}
    for path in sorted(glob.glob(str(ROOT / test_glob))):
        rel = str(pathlib.Path(path).resolve().relative_to(ROOT))
        try:
            tree = ast.parse(pathlib.Path(path).read_text(encoding='utf-8'), rel)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for d in node.decorator_list:
                    if isinstance(d, ast.Call) and _name(d.func) == 'positive_control' \
                            and d.args and isinstance(d.args[0], ast.Constant) \
                            and isinstance(d.args[0].value, str):
                        out.setdefault(d.args[0].value, []).append(
                            {'module': rel, 'function': node.name, 'line': node.lineno,
                             'form': 'decorator'})
                calls_observe = any(isinstance(sub, ast.Call) and _name(sub.func) == 'observe'
                                    for sub in ast.walk(node))
                if not calls_observe:
                    continue
                # A control names its detector somewhere in its body: as observe()'s literal
                # argument, or as a string constant held in a tuple the loop hands to observe.
                # Every string constant in the function shaped like <module>:<function>:<CODE>
                # counts; a name that is never observed at run time shows up as NOT_EXECUTED in
                # validate(), so a stray constant cannot validate anything by itself.
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Constant) and isinstance(sub.value, str) \
                            and _DETECTOR_RE.match(sub.value):
                        out.setdefault(sub.value, []).append(
                            {'module': rel, 'function': node.name, 'line': sub.lineno,
                             'form': 'observe'})
    return out


def _name(func) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ''


def hits(rid: str | None) -> list[dict]:
    p = hits_path()
    if not p.exists():
        return []
    rows = []
    for ln in p.read_text().splitlines():
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if rid is None or r.get('run_id') == rid:
            rows.append(r)
    return rows


def validate(rid: str | None, ran_modules, full_run: bool, write: bool = True) -> dict:
    """Per manifest detector: VALIDATED / UNVALIDATED_* / NOT_IN_THIS_RUN for the run `rid`.

    `ran_modules` is the set of test module paths (repo-relative) the run executed. On a partial
    run a detector whose every declared control lives in a module that did not run is
    NOT_IN_THIS_RUN and is not a failure; one whose control module ran but recorded no trip is.
    """
    manifest = load_manifest()
    decl = declared_controls()
    ran = {str(m) for m in ran_modules}
    seen = hits(rid)
    by_det: dict[str, list[dict]] = {}
    for h in seen:
        by_det.setdefault(h['detector'], []).append(h)
    rows, counts = [], {}
    for d in manifest:
        name = d['detector']
        controls = decl.get(name, [])
        obs = by_det.get(name, [])
        if not controls:
            status = NO_CONTROL
        elif any(h['tripped'] for h in obs):
            status = VALIDATED
        elif obs:
            status = DID_NOT_TRIP
        elif full_run or any(c['module'] in ran for c in controls):
            status = NOT_EXECUTED
        else:
            status = NOT_IN_RUN
        counts[status] = counts.get(status, 0) + 1
        rows.append({'detector': name, 'status': status, 'where': d.get('where'),
                     'controls_declared': controls,
                     'observations': [{k: h[k] for k in ('module', 'function', 'got', 'tripped')}
                                      for h in obs]})
    # What fails THIS run: every UNVALIDATED row on a full run; on a partial run only a control
    # that ran in it and did not trip, or a control module that ran and recorded nothing. A
    # detector with no control at all is a global fact, reported on every run and failing the
    # full run, which is the authoritative statement of rule 2.
    blocking = [r for r in rows if r['status'].startswith('UNVALIDATED')
                and (full_run or r['status'] in (DID_NOT_TRIP, NOT_EXECUTED))]
    unlisted = census(manifest)
    doc = {'ARTIFACT': 'DETECTOR_VALIDATION', 'spec_version': 'detector-validation-1',
           'run_id': rid, 'full_run': bool(full_run), 'blocking': [r['detector'] for r in blocking],
           'written_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'n_detectors': len(rows), 'counts': counts,
           'verdict': ('ALL_VALIDATED' if counts.get(VALIDATED, 0) == len(rows)
                       else 'PARTIAL_RUN_CLEAN' if (not full_run and not blocking)
                       else 'UNVALIDATED_DETECTORS_PRESENT'),
           'rows': rows,
           'census': unlisted,
           'RULE': ('a detector without a control that ran AND tripped in this run is not '
                    'validated; the suite fails on any UNVALIDATED_* row. NOT_IN_THIS_RUN '
                    'appears only on a partial (--only / --modules) run and is not a pass.')}
    if write:
        VALIDATION.write_text(json.dumps(doc, indent=1, sort_keys=True) + '\n')
    return doc


def census(manifest=None) -> dict:
    """Declared refusal codes in the guard trees that the manifest does not list: reported."""
    try:
        import sys
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from nfl.tools import invariant_manifest as IM
        declared = IM.declared_refusals()
    except Exception as e:  # noqa: BLE001
        return {'state': 'CENSUS_NOT_EXECUTED', 'error': f'{type(e).__name__}: {e}'}
    manifest = manifest if manifest is not None else load_manifest()
    listed = {d['detector'].rsplit(':', 1)[-1] for d in manifest}
    unlisted = sorted(c for c in declared if c not in listed)
    return {'state': 'CENSUS_MEASURED', 'n_declared_refusal_codes': len(declared),
            'n_listed_in_manifest': len(listed),
            'n_unlisted': len(unlisted),
            'unlisted_sample': unlisted[:40],
            'MEANING': ('unlisted codes are refusals this system ships that the rule is not yet '
                        'enforced for. They are reported here so the gap is visible; listing one '
                        'in DETECTORS.json puts it under the rule.')}
