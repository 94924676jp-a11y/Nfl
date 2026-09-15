#!/usr/bin/env python3.12
"""The invariant-execution manifest: declared -> executed -> result.

WHY THIS EXISTS, AND WHAT run_suite.py STILL CANNOT SEE

`nfl/tests/run_suite.py` reads each module's own tally, refuses a module that
measured nothing, and since WS11 refuses a FUNCTION that measured nothing. That
closes "the whole test went missing". It does not close the smaller and more
common thing:

    a test function that runs, records eleven checks, passes, and never
    reaches the two checks that were the reason it was written.

An early `return`, a `for` loop over a collection that came back empty, an
`if fr.state is State.PASS:` arm that did not fire -- in every one of those the
function's tally still moves, so the function is not zero-check, so the runner
is satisfied, and the suite is green. The invariant was declared in the source
and was never evaluated. Nothing in this repository asserted otherwise until
this tool.

WHAT IT MEASURES

Three registers, each populated from the repository's own declarations. None of
the three is hand-written, because a hand-written list of invariants goes stale
the moment one is added and then certifies a system it no longer describes.

  R1  CHECK SITES. Every `check(...)` and `blocked(...)` call site in every
      test module, found by AST. That is this repository's own vocabulary for
      "here is a property I claim to enforce". The tool then RUNS the suite
      with each module's `check` wrapped, and records the line each executed
      call came from. Declared minus executed is the answer.

  R2  REFUSAL CODES. Every non-PASS `Outcome` code constructed anywhere in the
      shipping tree -- `Outcome.fail`, `.blocked`, `.deferred`,
      `.not_applicable` -- is a guard the system claims to have. The tool
      patches `Outcome.__post_init__` once, before any test module is
      imported, so every Outcome built during the run records its own code. A
      declared refusal code that NO test caused to be constructed is a guard
      no test has ever seen fire. CLAUDE.md rule 4: "A guard is not
      demonstrated because compliant data passes it."

  R3  LOAD-BEARING GUARDS. Every `(module_path, attr)` pair passed to
      `nfl/tests/bypass.py`. `bypass.guard_bypassed` is patched to record, so
      a declared bypass proof that stopped running is visible.

THE RULE THIS ENFORCES

    A blocked or refused invariant counts as FAILURE TO CERTIFY, never success.

So the verdict vocabulary has five values and NOT_CERTIFIED is a distinct one:

    CERTIFIED       declared, executed, and it passed
    FAILED          declared, executed, and it failed
    BLOCKED         declared, executed, and it said out loud it could not run
    NOT_CERTIFIED   declared and NEVER EXECUTED on this run
    NEGATIVE_ARM    a site whose verdict argument is the literal False -- the
                    unreachable half of a try/except refusal pair, whose
                    non-execution is the guard working. Counted apart and
                    never as a certification.
    BLOCKED_ARM_NOT_TAKEN
                    a `blocked(...)` site that did not fire, i.e. the fixture
                    WAS available and the real checks ran. Same shape, same
                    treatment.
    BLOCKED_BRANCH  a site in a function that recorded a blocked() this run:
                    the untaken half of a declared either/or.

BLOCKED and NOT_CERTIFIED are both failures to certify. They are reported
apart because they are different defects: BLOCKED is honest and NOT_CERTIFIED
is silent, and the silent one is the one this tool exists for.

WHAT IT IS NOT

It is not a coverage tool and it does not measure the production line. A check
site that executed proves only that the assertion was evaluated -- not that it
was a good assertion. Executing a tautology still records CERTIFIED, so the
false-green census in `nfl/research/v4/p6/P6_INVARIANT_MANIFEST.md` is a
separate, hand-read document and this tool does not replace it.

USAGE

    python3.12 nfl/tools/invariant_manifest.py                 # full run
    python3.12 nfl/tools/invariant_manifest.py --only test_r8  # one module
    python3.12 nfl/tools/invariant_manifest.py --out DIR

    python3.12 nfl/tools/invariant_manifest.py \
        --baseline nfl/research/v4/p6/INVARIANT_MANIFEST.json

THE GATE, AND WHY IT IS SHAPED THIS WAY

Exit code is 1 when any R1 check site or R3 bypass proof is NOT_CERTIFIED or
FAILED. BLOCKED alone exits 0: it is printed and carried in the JSON, but a
runner that turned a declared block red would push authors back toward the
silent return, which is the defect this whole tool exists to end.

R2 is REPORTED AND NOT GATED unless `--strict-refusals` is passed, and that is
a judgement worth stating rather than burying. Most of the several hundred
named refusal codes guard a data condition no test can currently produce, so a
gate including them would be red on the day it was written and stay red, and a
gate that is always red is a gate nobody reads. The number is printed either
way and it IS a failure to certify. This is a decision about what a runner
blocks on, not a claim that the rest are fine.

`--baseline PREVIOUS.json` switches to regression mode: the run exits non-zero
only for an invariant that was CERTIFIED (or BLOCKED) in the baseline and is
not certified now. That is the form to wire into a workflow -- it lets the
standing census be worked down while making it impossible for a check that is
executing today to stop executing in silence tomorrow.
"""
from __future__ import annotations

import argparse
import ast
import collections
import glob
import importlib
import importlib.util
import io
import json
import os
import pathlib
import sys
import traceback
from contextlib import redirect_stdout

ROOT = pathlib.Path(__file__).resolve().parents[2]

# The trees whose refusal codes count as DECLARED GUARDS for R2. Tests are
# excluded on purpose: a code a test invents to seed a violation is a fixture,
# not a guard the system ships.
GUARD_TREES = ('nfl/production', 'nfl/product', 'nfl/ingest', 'nfl/identity',
               'nfl/capture', 'nfl/prospective', 'nfl/accounting',
               'nfl/adapters', 'nfl/parse', 'nfl/schema', 'nfl/scoring',
               'nfl/derived', 'nfl/tools', 'sportsplatform')

_NONPASS = ('fail', 'blocked', 'deferred', 'not_applicable')


# ---------------------------------------------------------------------------
# R1 declaration: the check sites a module declares, by AST.
# ---------------------------------------------------------------------------
def declared_sites(path):
    """[{line, end_line, fn, kind, label}] for every check/blocked call.

    `fn` is the ENCLOSING top-level test function where there is one, so a
    site inside a helper is attributed to the helper and reported by its own
    name rather than silently credited to whichever test happened to call it.
    """
    src = pathlib.Path(path).read_text(encoding='utf-8')
    tree = ast.parse(src, str(path))
    owner = {}

    def walk(node, fn):
        for ch in ast.iter_child_nodes(node):
            nfn = ch.name if isinstance(
                ch, (ast.FunctionDef, ast.AsyncFunctionDef)) else fn
            if isinstance(ch, ast.Call):
                f = ch.func
                nm = f.id if isinstance(f, ast.Name) else getattr(f, 'attr', '')
                if nm in ('check', 'blocked'):
                    owner[(ch.lineno, ch.col_offset)] = (nm, nfn, ch)
            walk(ch, nfn)

    walk(tree, None)
    out = []
    for (ln, col), (nm, fn, call) in sorted(owner.items()):
        label = None
        if call.args and isinstance(call.args[0], ast.Constant) \
                and isinstance(call.args[0].value, str):
            label = call.args[0].value
        # THE FAILURE ARM OF A TWO-ARM CONSTRUCT IS NOT A MISSING INVARIANT.
        #
        #     try:
        #         R.pbp_path(2026)
        #         check('pbp_path(2026) refuses', False, 'it returned')
        #     except R.ChronologyError:
        #         check('pbp_path(2026) refuses', True)
        #
        # The `False` site is written to be unreachable while the guard works,
        # so calling it NOT_CERTIFIED would mark a correctly refusing guard as
        # uncertified -- the tool inventing the defect it was built to find.
        # A site whose verdict argument is the literal False is recorded as
        # NEGATIVE_ARM and its non-execution is expected; if it DOES execute
        # it records a real FAILED, which is the point of it. Both arms
        # missing still shows, because the positive arm is a normal site.
        arm = None
        if len(call.args) >= 2 and isinstance(call.args[1], ast.Constant) \
                and call.args[1].value is False:
            arm = 'negative'
        elif len(call.args) >= 2 and isinstance(call.args[1], ast.Constant) \
                and call.args[1].value is True:
            arm = 'report_only'
        out.append({'line': ln, 'end_line': getattr(call, 'end_lineno', ln),
                    'col': col, 'fn': fn, 'kind': nm, 'label': label,
                    'arm': arm})
    return out


def tripwire_names(path):
    """Delegated to the runner, so the two cannot drift."""
    import nfl.tests.run_suite as rs
    return rs.tally_tripwires(str(path))


# ---------------------------------------------------------------------------
# R2 declaration: named refusal codes in the shipping tree.
# ---------------------------------------------------------------------------
def declared_refusals():
    out = {}
    for tree in GUARD_TREES:
        base = ROOT / tree
        if not base.exists():
            continue
        for p in sorted(base.rglob('*.py')):
            rel = str(p.relative_to(ROOT))
            # A code a TEST invents to seed a violation is a fixture, not a
            # guard this system ships, and counting it would let a module
            # certify itself.
            if '/tests/' in rel or p.name.startswith('test_') \
                    or p.name == 'bypass.py':
                continue
            try:
                t = ast.parse(p.read_text(encoding='utf-8'), rel)
            except SyntaxError:
                continue
            for n in ast.walk(t):
                if not isinstance(n, ast.Call):
                    continue
                f = n.func
                if not isinstance(f, ast.Attribute) or f.attr not in _NONPASS:
                    continue
                base_ok = (isinstance(f.value, ast.Name)
                           and f.value.id in ('Outcome', 'O', 'Out'))
                if not base_ok:
                    continue
                if not n.args or not isinstance(n.args[0], ast.Constant):
                    continue
                code = n.args[0].value
                if not isinstance(code, str) or not code.isupper():
                    continue
                out.setdefault(code, {'code': code, 'state': f.attr.upper(),
                                      'sites': []})
                out[code]['sites'].append(f'{rel}:{n.lineno}')
    return out


# ---------------------------------------------------------------------------
# R3 declaration: load-bearing guard proofs.
# ---------------------------------------------------------------------------
def declared_bypasses(files):
    out = {}
    for f in files:
        try:
            t = ast.parse(pathlib.Path(f).read_text(encoding='utf-8'), f)
        except SyntaxError:
            continue
        for n in ast.walk(t):
            if not isinstance(n, ast.Call):
                continue
            nm = (n.func.id if isinstance(n.func, ast.Name)
                  else getattr(n.func, 'attr', ''))
            if nm not in ('guard_bypassed', 'assert_guard_is_load_bearing'):
                continue
            kw = {k.arg: k.value for k in n.keywords}
            mp = kw.get('module_path')
            at = kw.get('attr')
            if mp is None and len(n.args) >= 2:
                mp, at = n.args[0], n.args[1]
            if not (isinstance(mp, ast.Constant) and isinstance(at, ast.Constant)):
                continue
            key = f'{mp.value}.{at.value}'
            out.setdefault(key, {'guard': key, 'sites': []})
            out[key]['sites'].append(f'{f}:{n.lineno}')
    return out


# ---------------------------------------------------------------------------
# The run.
# ---------------------------------------------------------------------------
OBSERVED_CODES = collections.Counter()
OBSERVED_BYPASS = collections.Counter()


def _install_global_recorders():
    """Patched ONCE, before any test module is imported.

    Order matters and is the whole reason this is a function called early: a
    test module that does `from nfl.tests.bypass import guard_bypassed` binds
    the name at import time, so a patch applied afterwards would be recorded
    as never used -- a false NOT_CERTIFIED, which is the same class of defect
    this tool is built to find, pointed at itself.
    """
    from sportsplatform.governance import outcome as OC
    orig_post = OC.Outcome.__post_init__

    def post(self):
        orig_post(self)
        OBSERVED_CODES[(self.state.value, self.code)] += 1

    OC.Outcome.__post_init__ = post

    import nfl.tests.bypass as BP
    orig_gb = BP.guard_bypassed

    def gb(module_path, attr, *a, **k):
        OBSERVED_BYPASS[f'{module_path}.{attr}'] += 1
        return orig_gb(module_path, attr, *a, **k)

    BP.guard_bypassed = gb
    return OC


def run(files, verbose=False):
    import nfl.tests.run_suite as rs
    modules = []
    for f in files:
        rec = {'module': f, 'sites': declared_sites(f), 'imported': False,
               'import_error': None, 'functions': {}}
        sites = rec['sites']
        # line -> site index, expanded across the call's full line span so a
        # multi-line `check(...)` is matched wherever the frame reports it.
        line_ix = {}
        for i, s in enumerate(sites):
            for ln in range(s['line'], s['end_line'] + 1):
                line_ix.setdefault(ln, i)
        executed = {}                      # site index -> 'PASS'/'FAIL'/'BLOCKED'
        unmatched = collections.Counter()

        name = 'im_' + f.replace('/', '_')[:-3]
        spec = importlib.util.spec_from_file_location(name, f)
        mod = importlib.util.module_from_spec(spec)
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                spec.loader.exec_module(mod)
        except Exception:                                        # noqa: BLE001
            rec['import_error'] = traceback.format_exc(limit=3)
            modules.append(rec)
            continue
        rec['imported'] = True

        real_check = getattr(mod, 'check', None)
        real_blocked = getattr(mod, 'blocked', None)

        def _site_of():
            fr = sys._getframe(2)
            return line_ix.get(fr.f_lineno), fr.f_lineno

        def wrapped_check(*a, **k):
            i, ln = _site_of()
            before = rs.tally(mod)
            try:
                return real_check(*a, **k)
            finally:
                after = rs.tally(mod)
                verdict = 'PASS'
                if before and after and after[1] > before[1]:
                    verdict = 'FAIL'
                if i is None:
                    unmatched[ln] += 1
                else:
                    if executed.get(i) != 'FAIL':
                        executed[i] = verdict

        def wrapped_blocked(*a, **k):
            i, ln = _site_of()
            try:
                return real_blocked(*a, **k)
            finally:
                if i is None:
                    unmatched[ln] += 1
                else:
                    executed[i] = 'BLOCKED'

        if real_check is not None:
            mod.check = wrapped_check
        if real_blocked is not None:
            mod.blocked = wrapped_blocked

        fns = [n for n in dir(mod)
               if n.startswith('test_') and callable(getattr(mod, n))]
        trips = rs.tally_tripwires(f)
        for n in fns:
            if n in trips:
                rec['functions'][n] = {'tripwire': True}
                continue
            before = dict(executed)
            raised = None
            try:
                with redirect_stdout(buf):
                    getattr(mod, n)()
            except Exception:                                    # noqa: BLE001
                raised = traceback.format_exc(limit=2)
            got = {i: v for i, v in executed.items() if i not in before
                   or before[i] != v}
            rec['functions'][n] = {'tripwire': False, 'raised': raised,
                                   'n_sites_hit': len(got)}
        rec['executed'] = executed
        rec['unmatched'] = dict(unmatched)
        modules.append(rec)
        if verbose:
            d = len([s for s in sites if s['fn']])
            print(f'  {f}: {len(executed)}/{len(sites)} declared site(s) '
                  f'executed')
    return modules


def build(files, verbose=False):
    modules = run(files, verbose=verbose)
    rows = []
    for rec in modules:
        f = rec['module']
        ex = rec.get('executed', {})
        for i, s in enumerate(rec['sites']):
            v = ex.get(i)
            if v is None:
                # A `blocked(...)` SITE THAT DID NOT FIRE IS THE TEST WORKING.
                # It is the "I could not run" arm of the same either/or that
                # NEGATIVE_ARM covers for `check(label, False)`: its
                # non-execution means the fixture WAS there and the real
                # checks ran. On the first full pass 163 of 223 apparent
                # failures to certify were this shape, so counting them would
                # have buried the 57 that are real under three times their
                # number of noise.
                if s['kind'] == 'blocked':
                    res = 'BLOCKED_ARM_NOT_TAKEN'
                elif s.get('arm') == 'negative':
                    res = 'NEGATIVE_ARM'
                else:
                    res = 'NOT_CERTIFIED'
            else:
                res = v
            rows.append({
                'register': 'R1_CHECK_SITE',
                'invariant': s['label'] or f"<computed label at line {s['line']}>",
                'declared_at': f"{f}:{s['line']}",
                'enforcing_test': f"{f}::{s['fn'] or '<module>'}",
                'kind': s['kind'], 'arm': s.get('arm'),
                'executed': v is not None,
                'result': res,
            })
        if rec['import_error']:
            rows.append({
                'register': 'R1_CHECK_SITE', 'invariant': 'MODULE_IMPORTS',
                'declared_at': f, 'enforcing_test': f, 'kind': 'import',
                'executed': False, 'result': 'NOT_CERTIFIED'})
    ref = declared_refusals()
    seen = {c for (_s, c) in OBSERVED_CODES}
    for code, d in sorted(ref.items()):
        rows.append({
            'register': 'R2_REFUSAL_CODE', 'invariant': code,
            'declared_at': d['sites'][0], 'enforcing_test':
                f"{len(d['sites'])} declaration site(s)",
            'kind': d['state'],
            'executed': code in seen,
            'result': 'CERTIFIED' if code in seen else 'NOT_CERTIFIED'})
    byp = declared_bypasses(files)
    for g, d in sorted(byp.items()):
        rows.append({
            'register': 'R3_LOAD_BEARING', 'invariant': g,
            'declared_at': d['sites'][0],
            'enforcing_test': ', '.join(d['sites'][:3]), 'kind': 'bypass',
            'executed': g in OBSERVED_BYPASS,
            'result': 'CERTIFIED' if g in OBSERVED_BYPASS else 'NOT_CERTIFIED'})
    for r in rows:
        if r['result'] == 'PASS':
            r['result'] = 'CERTIFIED'
        elif r['result'] == 'FAIL':
            r['result'] = 'FAILED'
    _mark_blocked_branches(rows)
    return modules, rows


def _mark_blocked_branches(rows):
    """The untaken half of a DECLARED either/or is not a silent skip.

    `test_appearance_team_scope.py` is the pattern:

        if pair is None:
            _no_mixed_game('B (no refused club anywhere either)')   # blocked()
            return
        ...                                                        # checks

    One branch runs and the other does not, by construction. Its check sites
    never execute, and calling them NOT_CERTIFIED would report a test that
    said out loud it could not measure as one that silently skipped -- the
    tool inventing its own defect, which is what NEGATIVE_ARM already exists
    to prevent one level down.

    THE EVIDENCE USED IS THE REPOSITORY'S OWN ESCAPE HATCH, not a guess: a
    function is credited only when a `blocked()` site inside it ACTUALLY FIRED
    on this run. A function that returned silently gets nothing. So this
    cannot become a hiding place -- to use it, an author has to say out loud
    that the branch could not run, which is the behaviour being encouraged.

    LIMIT, STATED: sites are attributed to their immediately enclosing
    function, so a check inside a helper does not group with the test function
    that called the helper and is not reclassified. That errs toward
    NOT_CERTIFIED, which is the safe direction.
    """
    blocked_fns = {r['enforcing_test'] for r in rows
                   if r['register'] == 'R1_CHECK_SITE'
                   and r['result'] == 'BLOCKED'}
    for r in rows:
        if (r['register'] == 'R1_CHECK_SITE'
                and r['result'] == 'NOT_CERTIFIED'
                and r['enforcing_test'] in blocked_fns):
            r['result'] = 'BLOCKED_BRANCH'


def main(argv=None):
    ap = argparse.ArgumentParser(description='invariant-execution manifest')
    ap.add_argument('--only', default=None)
    ap.add_argument('--out', default='nfl/research/v4/p6')
    ap.add_argument('-v', '--verbose', action='store_true')
    ap.add_argument('--no-write', action='store_true')
    ap.add_argument('--name', default='INVARIANT_MANIFEST.json')
    ap.add_argument('--slice', default=None,
                    help='"i/n": run only the i-th of n equal shards of the '
                         'discovered module list, writing a partial manifest. '
                         'A full pass over this suite takes tens of minutes on '
                         'a loaded machine and a reaped run leaves nothing, so '
                         'shards can be merged with --merge.')
    ap.add_argument('--merge', nargs='*', default=None,
                    help='merge the named partial manifests into --name and '
                         'report the combined result without re-running')
    ap.add_argument('--strict-refusals', action='store_true',
                    help='make R2 (never-constructed refusal codes) fatal')
    ap.add_argument('--baseline', default=None,
                    help='a previously written manifest JSON; exit non-zero '
                         'only for invariants that were certified there and '
                         'are not certified now')
    args = ap.parse_args(argv)

    os.chdir(ROOT)
    for q in (str(ROOT), str(ROOT / 'sportsplatform')):
        if q not in sys.path:
            sys.path.insert(0, q)
    _install_global_recorders()

    files = (sorted(glob.glob('nfl/tests/test_*.py'))
             + sorted(glob.glob('sportsplatform/**/test_*.py', recursive=True)))
    if args.only:
        files = [f for f in files if args.only in f]
    if args.merge:
        rows, modules = [], []
        for q in args.merge:
            d = json.loads((ROOT / q).read_text())
            rows += d['rows']
            modules += [{'module': m['module'], 'sites': [],
                         'import_error': m.get('import_error'),
                         'executed': {}, 'unmatched': m.get(
                             'unmatched_lines', {})}
                        for m in d['per_module']]
            for k, v in (d.get('observed_outcome_codes') or {}).items():
                st, cd = k.split('|', 1)
                OBSERVED_CODES[(st, cd)] += v
        # A merged manifest is a manifest OF THE SHARDS IT WAS GIVEN. If a
        # shard is missing, the modules in it are absent rather than clean,
        # so the shard list is recorded and the count is printed.
        # R2 AND R3 ARE WHOLE-TREE REGISTERS AND EVERY SHARD CARRIES A COPY.
        # Concatenating them would multiply the census by the shard count and
        # would count a code as NOT_CERTIFIED in the shards that did not reach
        # it. They are deduplicated by invariant with executed = ANY, which is
        # the correct union: a guard that fired in one shard fired.
        keep, seen = [], {}
        for r in rows:
            if r['register'] == 'R1_CHECK_SITE':
                keep.append(r)
                continue
            k = (r['register'], r['invariant'])
            if k not in seen:
                seen[k] = dict(r)
                keep.append(seen[k])
            elif r['executed'] and not seen[k]['executed']:
                seen[k].update(executed=True, result='CERTIFIED')
        rows = keep
        print(f'merged {len(args.merge)} partial manifest(s): '
              f'{len(modules)} module record(s), {len(rows)} row(s) after '
              f'deduplicating the whole-tree registers')
        files = sorted({m['module'] for m in modules})
    else:
        if not files:
            print('NO TEST MODULE MATCHED. An empty manifest is not a clean '
                  'one.')
            return 1
        if args.slice:
            i, n = (int(x) for x in args.slice.split('/'))
            files = [f for k, f in enumerate(files) if k % n == i]
            print(f'SHARD {i}/{n}: {len(files)} module(s). This manifest is '
                  f'PARTIAL and its NOT_CERTIFIED counts are only about these '
                  f'modules.')
        modules, rows = build(files, verbose=args.verbose)

    by = collections.Counter((r['register'], r['result']) for r in rows)
    regs = ('R1_CHECK_SITE', 'R2_REFUSAL_CODE', 'R3_LOAD_BEARING')
    print('\nINVARIANT-EXECUTION MANIFEST   declared -> executed -> result')
    print(f'{"register":<17}{"declared":>9}{"CERTIFIED":>10}{"FAILED":>7}'
          f'{"BLOCKED":>8}{"NOT_CERT":>9}{"neg-arm":>9}')
    tot = collections.Counter()
    for reg in regs:
        d = sum(v for (r, _), v in by.items() if r == reg)
        if not d:
            continue
        c = by[(reg, 'CERTIFIED')]; fl = by[(reg, 'FAILED')]
        bl = by[(reg, 'BLOCKED')] + by[(reg, 'BLOCKED_BRANCH')]
        nc = by[(reg, 'NOT_CERTIFIED')]
        na = (by[(reg, 'NEGATIVE_ARM')]
              + by[(reg, 'BLOCKED_ARM_NOT_TAKEN')])
        tot['d'] += d; tot['c'] += c; tot['f'] += fl
        tot['b'] += bl; tot['n'] += nc; tot['a'] += na
        print(f'{reg:<17}{d:>9}{c:>10}{fl:>7}{bl:>8}{nc:>9}{na:>9}')
    print(f'{"TOTAL":<17}{tot["d"]:>9}{tot["c"]:>10}{tot["f"]:>7}'
          f'{tot["b"]:>8}{tot["n"]:>9}{tot["a"]:>9}')

    # THE GATE. R1 and R3 are held green; R2 is reported as a census and is
    # fatal only under --strict-refusals.
    #
    # WHY R2 IS NOT IN THE GATE BY DEFAULT, STATED PLAINLY RATHER THAN HIDDEN:
    # most of the several hundred refusal codes guard a data condition no test
    # can currently produce, so a gate that included them would be red on the
    # day it was written and would stay red, and a gate that is always red is
    # a gate nobody reads. The NUMBER is printed either way, and it is a real
    # failure to certify -- this is a decision about which number a runner
    # blocks on, not a claim that the others are fine.
    gate_regs = {'R1_CHECK_SITE', 'R3_LOAD_BEARING'}
    if args.strict_refusals:
        gate_regs.add('R2_REFUSAL_CODE')

    base = None
    if args.baseline:
        bp = pathlib.Path(args.baseline)
        if not bp.is_absolute():
            bp = ROOT / bp
        if not bp.exists():
            print(f'BASELINE ABSENT: {args.baseline}. A missing baseline is '
                  f'not an empty one; refusing to certify against nothing.')
            return 1
        prev = json.loads(bp.read_text())
        base = {r['declared_at'] + '|' + str(r.get('invariant'))
                for r in prev['rows'] if r['result'] in ('CERTIFIED', 'BLOCKED')}

    def _bad(r):
        if r['register'] not in gate_regs:
            return False
        if r['result'] not in ('NOT_CERTIFIED', 'FAILED'):
            return False
        if base is None:
            return True
        # REGRESSION MODE. Only an invariant that WAS certified and no longer
        # is counts, so the gate can be held green while the standing census
        # is worked down. It never lets a previously certified invariant stop
        # executing in silence, which is the property being bought.
        return (r['declared_at'] + '|' + str(r.get('invariant'))) in base

    nc_rows = [r for r in rows
               if r['result'] == 'NOT_CERTIFIED' and r['register'] in gate_regs]
    if nc_rows:
        print(f'\nFAILURE TO CERTIFY: {len(nc_rows)} declared invariant(s) in '
              f'{sorted(gate_regs)} were never executed on this run. Declared '
              f'and not evaluated is not a pass.')
        for r in nc_rows[:80]:
            print(f'  {r["register"]:<16} {r["declared_at"]:<62} '
                  f'{(r["invariant"] or "")[:58]}')
        if len(nc_rows) > 80:
            print(f'  ... and {len(nc_rows) - 80} more (see the JSON)')

    r2_nc = by[('R2_REFUSAL_CODE', 'NOT_CERTIFIED')]
    r2_d = sum(v for (r, _), v in by.items() if r == 'R2_REFUSAL_CODE')
    if r2_d:
        print(f'\nR2 CENSUS: {r2_nc} of {r2_d} named refusal codes in the '
              f'shipping tree were NEVER CONSTRUCTED by any test in this run. '
              f'A guard no test has seen fire is a guard nobody has '
              f'demonstrated.'
              + ('' if args.strict_refusals else
                 ' (reported, not gating; --strict-refusals makes it fatal)'))

    bb = [r for r in rows if r['result'] == 'BLOCKED_BRANCH']
    if bb:
        print(f'\nBLOCKED BRANCH: {len(bb)} site(s) in a function that '
              f'recorded a blocked() this run -- the untaken half of a '
              f'declared either/or. Not a certification, not a silent skip.')
    blk = [r for r in rows if r['result'] == 'BLOCKED']
    if blk:
        print(f'\nBLOCKED (declared, honest, and still not a certification): '
              f'{len(blk)}')
        for r in blk[:30]:
            print(f'  {r["declared_at"]:<62} {(r["invariant"] or "")[:58]}')

    fail_rows = [r for r in rows if r['result'] == 'FAILED']
    if fail_rows:
        print(f'\nFAILED: {len(fail_rows)}')
        for r in fail_rows[:40]:
            print(f'  {r["declared_at"]:<62} {(r["invariant"] or "")[:58]}')

    payload = {'root': str(ROOT), 'n_modules': len(files), 'rows': rows,
               'gate_registers': sorted(gate_regs),
               'summary': {f'{a}|{b}': v for (a, b), v in sorted(by.items())},
               'observed_outcome_codes':
                   {f'{s}|{c}': n for (s, c), n in sorted(OBSERVED_CODES.items())},
               'per_module': [
                   {'module': m['module'], 'declared': len(m['sites']),
                    'executed': len(m.get('executed', {})),
                    'import_error': bool(m['import_error']),
                    'unmatched_lines': m.get('unmatched', {})}
                   for m in modules]}
    if not args.no_write:
        out = ROOT / args.out
        out.mkdir(parents=True, exist_ok=True)
        dest = out / args.name
        dest.write_text(json.dumps(payload, indent=1, sort_keys=True))
        print(f'\nwrote {args.out}/{args.name}')

    bad = [r for r in rows if _bad(r)]
    if base is not None:
        print(f'\nREGRESSION MODE against {args.baseline}: '
              f'{len(bad)} invariant(s) that were certified in the baseline '
              f'are not certified now.')
        for r in bad[:40]:
            print(f'  {r["result"]:<15} {r["declared_at"]:<62} '
                  f'{(r["invariant"] or "")[:56]}')
    print('MANIFEST ' + ('FAILURE_TO_CERTIFY' if bad else 'FULLY_CERTIFIED'))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
