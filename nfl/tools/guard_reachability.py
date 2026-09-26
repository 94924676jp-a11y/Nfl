#!/usr/bin/env python3.12
"""Which guards actually protect something, and what happens when they fail.

A guard that is not on the execution path is documentation. A guard whose
failure does not stop the protected action is metadata. Neither is visible from
reading the guard, and neither is visible from its tests passing -- DEF-065 was
a control that was present, correct, tested, written into the output artifact,
and protected nothing, because `main()` never branched on it.

So this measures three separate things and refuses to collapse them:

  1. DOES IT EXIST          every `assert_*` definition in the production tree
  2. IS IT CALLED           by production, by tests, by research, or by nobody
  3. DOES FAILURE STOP      what the caller does with the result

(3) is the one that cannot be guessed, and it turns on a distinction that
matters more than it looks:

  A guard that RAISES is load-bearing even when called as a bare statement,
  because the exception is the stop. A guard that RETURNS an Outcome is
  load-bearing only if the caller branches on it -- and a bare call to one of
  those is exactly DEF-065.

So each guard is classified by HOW IT FAILS first, and only then by what its
callers do.

EFFECT VOCABULARY, per production call site:

  STOP       the failure returns, raises, or propagates out of the caller
  DOWNGRADE  the failure changes what the caller does without stopping it
  ANNOTATE   the result is stored or printed and execution continues
  NOTHING    the result is discarded and the guard cannot raise

Read `NOTHING` on a returning guard as the DEF-065 shape. Read `ANNOTATE` the
same way: writing a FAIL into the artifact you then publish is the defect, not
a mitigation of it.

WHAT THIS TOOL DOES NOT DECIDE. It cannot tell an ORPHANED_CONTROL from a
deliberate ADVISORY one, because that is a statement of intent and intent is
not in the syntax. It reports the measurement and leaves the classification to
a human reading it, which is why the output carries a NOT_ESTABLISHED column
rather than a guess.
"""
from __future__ import annotations

import ast
import collections
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PROD_DIRS = ('nfl/production', 'nfl/dfs', 'nfl/postgame', 'nfl/product',
             'nfl/governance', 'nfl/prospective', 'sportsplatform',
             'coordination')

STOP, DOWNGRADE, ANNOTATE, NOTHING = 'STOP', 'DOWNGRADE', 'ANNOTATE', 'NOTHING'
#: A FIFTH EFFECT, and leaving it out made the first census badly wrong.
#:
#: nfl/production/verdict.py is a verdict registry WITH ENFORCEMENT:
#: `from_outcome` maps a governance Outcome onto a gate result, `CLEARING` is
#: ('PASS',) alone, and `assess()` refuses a scope when any required gate is not
#: clearing -- with a gate ABSENT from the dict counted NOT_EVALUATED, never
#: assumed passing. So a guard whose Outcome is registered under a gate name is
#: load-bearing THROUGH THE REGISTRY, even though the calling line only stores
#: it.
#:
#: Without this, five guards in universe/run_chain.py read as ANNOTATE -- the
#: DEF-065 shape -- when they are in fact wired to INACTIVE_APPLICATION,
#: ROLE_PLAUSIBILITY, PARTICIPATION_COMPLETENESS, OPPORTUNITY_CONSERVATION and
#: REDISTRIBUTION_PLAUSIBILITY. Reporting those as unprotected would have been a
#: false accusation against working governance, which is the mirror image of the
#: defect this tool hunts.
VERDICT = 'VERDICT_REGISTERED'
try:
    sys.path.insert(0, str(ROOT))
    from nfl.production import verdict as _V
    REGISTERED_GATES = frozenset(_V.GATE_SCOPE)
except Exception:                                            # noqa: BLE001
    REGISTERED_GATES = frozenset()


#: DECLARED, NOT DERIVED. Three things in this census are judgements, and a
#: tool that guessed them would manufacture exactly the false confidence the
#: census exists to strip out. So they live in version control, defaulting to
#: NOT_ESTABLISHED, and every entry names its evidence.

#: guard -> the suite that proves `bad state -> guard FAIL -> action does not
#: happen`. NOT a unit test of the guard: an end-to-end proof that the
#: PROTECTED ACTION is prevented. A unit test showing the guard returns FAIL is
#: recorded as direct coverage instead, because DEF-065 was a guard whose unit
#: tests all passed while publication went ahead anyway.
LOAD_BEARING_PROOFS = {
    'assert_no_inactive_in_playable':
        'nfl/tests/test_publication_refusal_is_load_bearing.py',
    'assert_shared_draws':
        'nfl/tests/test_publication_refusal_is_load_bearing.py',
    'assert_graded_row':
        'nfl/tests/test_missing_is_not_zero.py',
    'nfl/production/nonqb/current_season_team_volume.py::assert_publishable':
        'nfl/tests/test_publishable_guards_are_load_bearing.py',
}

#: guard -> classification, with the reason. Absent means NOT_ESTABLISHED.
CLASSIFICATION = {
    'assert_metric_origin_complete': ('TEST_NOT_RUNTIME',
        'zero arguments; compares module constants, so its verdict is a '
        'property of the source and cannot differ between two runs'),
    'assert_no_inactive_survived': ('SUPERSEDED',
        'DEF-064; assert_no_inactive_in_playable is wired and STOPs'),
    'assert_ranking_admissible': ('ORPHANED_CONTROL',
        'logic proven, nothing calls it; wiring is a product decision about '
        'what the ranking is for'),
    'assert_live_lineage': ('ORPHANED_CONTROL',
        'reads the capture branch; wiring belongs with the open D24 items'),
    'assert_prospective_matches_frozen': ('CANDIDATE_SCOPED',
        'guards Candidate B against the accepted walk, and Candidate B has no '
        'production caller either'),
    'assert_no_inactive_in_playable': ('LOAD_BEARING',
        'bad state -> FAIL -> emit_package.main writes no artifact, proven by '
        'running it and inspecting the disk'),
    'assert_shared_draws': ('LOAD_BEARING',
        'same proof; note its kicker coverage is EMPTY because `kicking` is '
        'both a football layer and DK-bearing, so dk-foot subtracts the row '
        'from itself'),
    'assert_graded_row': ('LOAD_BEARING',
        'raises AnonymousZero at the point a graded row is emitted; a stranger '
        'id is refused rather than zeroed, proven through the real grader'),
    'nfl/production/nonqb/current_season_team_volume.py::assert_publishable': (
        'LOAD_BEARING',
        'the DOWNGRADE at run_forecast.py:1587 CHAINS INTO A STOP: a non-PASS '
        'verdict leaves verified_inputs empty, denom_panel stays declared '
        'blocked in freshness.REGISTRY, assert_fresh then BLOCKS and '
        'run_forecast returns a fatal outcome before any world is drawn. The '
        'two arms were run and differ, and a non-PASS outcome smuggled in '
        'under the right key is still refused -- a key is not a verification'),
    'nfl/production/nonqb/layers.py::assert_publishable': ('ADVISORY',
        'its verdict is written into g[publication_gate] as a string and no '
        'branch, assert or raise consults it, while the same function refuses '
        '25 other ways -- so it does NOT stop the artifact its docstring says '
        'can never exist. It is redundant rather than missing: the only '
        'production route to test_only is --dry-run, which run_forecast tags '
        'and q9shadow.ledger.assert_not_dry_run refuses as evidence. The '
        'redundancy is safe only while run_forecast passes injuries_rows=None '
        'and keeps tagging the dry run, and both are pinned in the test'),
}

#: test path -> determinism. Absent means NOT_ESTABLISHED: not a claim of
#: determinism, an absence of one.
TEST_DETERMINISM = {
    'nfl/tests/test_publication_refusal_is_load_bearing.py': (
        'DETERMINISTIC_MEASURED',
        '16 checks, 8 runs -- 5 idle and 3 under 6 busy loops -- identical. No '
        'subprocess, no generated artifact, and every assertion checks the '
        'output path was empty immediately before the call'),
    'nfl/tests/test_missing_is_not_zero.py': (
        'DETERMINISTIC_MEASURED',
        '38 checks, 8 runs across idle and loaded, identical. Reads the sealed '
        'artifact, which is committed rather than generated'),
    'nfl/tests/test_artifact_claim.py': (
        'DETERMINISTIC_SINCE_DEF_070',
        'the SIGPIPE race is forced by exceeding the pipe buffer; 13 passes '
        'across idle and loaded conditions that previously gave both verdicts'),
    'nfl/tests/test_appearance_candidate_b.py': (
        'ENVIRONMENT_SENSITIVE',
        'a Q9 frozen blob resolves or not depending on run order; observed '
        'both 1-failing and 0-failing on unchanged code'),
    'nfl/tests/test_full_slate_rehearsal.py': (
        'GENERATED_ARTIFACT_SENSITIVE',
        'qb_v1 wants the gitignored nfl/research/p4b/panel_enriched.pkl, so it '
        'raises when run in isolation and not after a full pass'),
}


def kind(path: str) -> str:
    if '/tests/' in path or pathlib.Path(path).name.startswith('test_'):
        return 'test'
    if path.startswith(('nfl/research', 'nfl/tools')):
        return 'research'
    return 'prod'


def alias_map(tree) -> dict:
    """alias -> module path, for this file's imports.

    NEEDED BECAUSE TWO GUARDS CAN SHARE A NAME. `assert_publishable` is defined
    twice -- once in current_season_team_volume (takes a team-volume Outcome)
    and once in layers (takes eight layer Outcomes) -- and so is
    `assert_complete`. Keying the census on the bare name merged two different
    functions into one row, so a call site belonging to one was attributed to
    the other. `LY.assert_publishable(...)` resolves through `LY` to the file
    that actually defines it.
    """
    out = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module:
            for a in n.names:
                mod = f'{n.module}.{a.name}'.replace('.', '/') + '.py'
                if (ROOT / mod).exists():
                    out[a.asname or a.name] = mod
        elif isinstance(n, ast.Import):
            for a in n.names:
                mod = a.name.replace('.', '/') + '.py'
                if (ROOT / mod).exists():
                    out[a.asname or a.name] = mod
    return out


def _parse(p: pathlib.Path):
    try:
        return ast.parse(p.read_text(errors='replace'))
    except SyntaxError:
        return None


def definitions() -> dict:
    """guard name -> [{file, lineno, raises, returns_outcome}]"""
    out = collections.defaultdict(list)
    for d in PROD_DIRS:
        base = ROOT / d
        if not base.exists():
            continue
        for p in base.rglob('*.py'):
            if '__pycache__' in str(p):
                continue
            t = _parse(p)
            if t is None:
                continue
            for n in t.body if False else ast.walk(t):
                if not isinstance(n, ast.FunctionDef):
                    continue
                if not n.name.startswith('assert_'):
                    continue
                raises = any(isinstance(x, ast.Raise) for x in ast.walk(n))
                # a guard that RETURNS something is one whose caller must look
                returns = any(isinstance(x, ast.Return) and x.value is not None
                              for x in ast.walk(n))
                doc = (ast.get_docstring(n) or '').strip()
                out[n.name].append({
                    'file': str(p.relative_to(ROOT)),
                    'lineno': n.lineno,
                    'raises': raises,
                    'returns_a_value': returns,
                    # WHAT IT CLAIMS TO PROTECT, in the author's own words. A
                    # census that summarised this itself would be paraphrasing
                    # intent, and intent is the one thing the source states
                    # better than a tool can.
                    'protects': doc.splitlines()[0] if doc else ''})
    return dict(out)


def _effect(parent, call, target_name) -> str:
    """What the enclosing statement does with this guard's result."""
    # bare expression statement: the result is dropped
    if isinstance(parent, ast.Expr):
        return NOTHING
    # returned straight out of the caller
    if isinstance(parent, ast.Return):
        return STOP
    if isinstance(parent, (ast.Raise, ast.Assert)):
        return STOP
    return ANNOTATE if target_name is None else None


def call_sites(defs: dict) -> dict:
    """guard -> list of {file, lineno, kind, effect}"""
    sites = collections.defaultdict(list)
    for p in ROOT.rglob('*.py'):
        if '__pycache__' in str(p):
            continue
        t = _parse(p)
        if t is None:
            continue
        rel = str(p.relative_to(ROOT))
        k = kind(rel)
        # map child -> parent so a call's statement context is reachable
        parent = {}
        for node in ast.walk(t):
            for ch in ast.iter_child_nodes(node):
                parent[ch] = node
        aliases = alias_map(t)
        for n in ast.walk(t):
            if not isinstance(n, ast.Call):
                continue
            f = n.func
            nm = (f.attr if isinstance(f, ast.Attribute)
                  else f.id if isinstance(f, ast.Name) else None)
            if nm not in defs:
                continue
            # WHICH definition, when the name is defined more than once.
            resolved = None
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
                cand = aliases.get(f.value.id)
                if cand and any(d['file'] == cand for d in defs[nm]):
                    resolved = cand
            elif len(defs[nm]) == 1:
                resolved = defs[nm][0]['file']
            # walk up to the enclosing statement
            cur, target = n, None
            while cur in parent and not isinstance(parent[cur], ast.stmt):
                cur = parent[cur]
            stmt = parent.get(cur)
            if isinstance(stmt, ast.Assign):
                tg = stmt.targets[0]
                # TUPLE UNPACKING. `legal, _why = assert_roster_legal(...)`
                # made `target` the literal string 'legal, _why', which matches
                # no `if` test, so a guard that genuinely STOPs the optimizer
                # read as ANNOTATE. Any guard returning (ok, why) was misread
                # the same way. Each bound name is now a candidate.
                if isinstance(tg, ast.Tuple):
                    target = [e.id for e in tg.elts if isinstance(e, ast.Name)]
                else:
                    target = (tg.id if isinstance(tg, ast.Name)
                              else ast.unparse(tg))
            eff = _effect(stmt, n, target)
            if eff is None:
                eff = _traced_effect(t, stmt, target)
            gate = _registered_gate(t, stmt, target)
            if gate and eff in (ANNOTATE, NOTHING, None):
                eff = f'{VERDICT}:{gate}'
            sites[nm].append({'file': rel, 'lineno': n.lineno, 'kind': k,
                              'effect': eff, 'bound_to': target,
                              'resolves_to': resolved})
    return dict(sites)


def _registered_gate(tree, stmt, target):
    """Does this guard's Outcome reach `from_outcome` under a gate name?

    The pattern in run_chain.py is:

        inact = CV.assert_no_inactive_survives(...)
        L['inactive_application'] = {...}            # the ANNOTATE a reader sees
        G['INACTIVE_APPLICATION'] = V.from_outcome(inact)   # the enforcement

    Only the second line makes the guard load-bearing, and it is a separate
    statement from the call, so a per-site rule cannot see it.
    """
    if isinstance(target, list):
        for t in target:
            g = _registered_gate(tree, stmt, t)
            if g:
                return g
        return None
    if not target:
        return None
    base = target.split('.')[0].split('[')[0]
    fn = None
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.lineno <= stmt.lineno \
                and (n.end_lineno or n.lineno) >= stmt.lineno:
            if fn is None or n.lineno > fn.lineno:
                fn = n
    for n in ast.walk(fn or tree):
        if not isinstance(n, ast.Assign):
            continue
        v = n.value
        if not (isinstance(v, ast.Call)
                and getattr(v.func, 'attr', getattr(v.func, 'id', None))
                == 'from_outcome'):
            continue
        if base not in ast.unparse(v):
            continue
        tg = n.targets[0]
        if isinstance(tg, ast.Subscript) and isinstance(tg.slice, ast.Constant):
            return str(tg.slice.value)
        return 'UNNAMED_GATE'
    # ONE APPEND HOP. run_chain aggregates per-room verdicts before registering
    # them:  alloc_states.append(cg) ... G['OPPORTUNITY_CONSERVATION'] = <agg of
    # alloc_states>.  Without following that, two conservation guards read as
    # ANNOTATE when they are wired to a required gate. Only ONE hop is followed
    # on purpose: a longer chain is not something a syntax walk should claim to
    # understand, and a wrong LOAD_BEARING is worse than a NOT_ESTABLISHED.
    for n in ast.walk(fn or tree):
        if not (isinstance(n, ast.Call)
                and getattr(n.func, 'attr', None) == 'append'
                and n.args and base in ast.unparse(n.args[0])):
            continue
        acc = ast.unparse(n.func.value).split('.')[0]
        for m in ast.walk(fn or tree):
            if isinstance(m, ast.Assign) and acc in ast.unparse(m.value):
                tg = m.targets[0]
                if isinstance(tg, ast.Subscript) \
                        and isinstance(tg.slice, ast.Constant):
                    return str(tg.slice.value)
    return None


def _traced_effect(tree, stmt, target) -> str:
    """The result was bound to a name. Is that name ever branched on?

    `target` may be a LIST when the call was tuple-unpacked, in which case the
    strongest effect over the bound names wins: `legal, why = guard(...)` is a
    stop if `legal` is branched on, whatever happens to `why`.
    """
    if isinstance(target, list):
        best = None
        order = {STOP: 3, DOWNGRADE: 2, ANNOTATE: 1}
        for t in target:
            e = _traced_effect(tree, stmt, t)
            if best is None or order.get(e, 0) > order.get(best, 0):
                best = e
        return best or ANNOTATE
    if not target:
        return ANNOTATE
    fn = None
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.lineno <= stmt.lineno \
                and (n.end_lineno or n.lineno) >= stmt.lineno:
            if fn is None or n.lineno > fn.lineno:
                fn = n
    scope = fn or tree
    base = target.split('.')[0].split('[')[0]
    # A TERNARY IS A BRANCH, and missing that produced a false ANNOTATE on a
    # guard called `publishable` sitting on the production forecast path.
    #
    # run_forecast does:
    #     _tvp = _TV.assert_publishable(...)
    #     fx['_cs6_team_volume'] = {..., 'publishable': f'{_tvp.state...}'}
    #     _verified = ({...} if _tvp.state is State.PASS else {})
    #     _fresh = _CSE.assert_fresh(..., verified_inputs=_verified)
    #
    # The dict write is an annotation; the CONDITIONAL EXPRESSION is the
    # enforcement -- a non-PASS empties the verified-inputs set handed to the
    # next guard. Reading only `ast.If` saw the first and not the second, and
    # would have accused a working control of protecting nothing. So `IfExp` is
    # walked too, and a guard whose result conditions a value passed onward is
    # DOWNGRADE rather than ANNOTATE: it changes what happens without itself
    # returning.
    # ORDER MATTERS AND I GOT IT WRONG FIRST. Checking IfExp before the `if`
    # statements dropped STOP from 36 to 31: a guard that has BOTH a ternary
    # mentioning it AND an `if ...: return` was being called DOWNGRADE. The
    # strongest evidence has to win, so stopping branches are searched first.
    downgrade = False
    for n in ast.walk(scope):
        if not isinstance(n, ast.If):
            continue
        if base not in ast.unparse(n.test):
            continue
        body = list(ast.walk(ast.Module(body=n.body, type_ignores=[])))
        if any(isinstance(x, (ast.Return, ast.Raise)) for x in body):
            return STOP
        downgrade = True
    for n in ast.walk(scope):
        if isinstance(n, ast.IfExp) and base in ast.unparse(n.test):
            downgrade = True
    if downgrade:
        return DOWNGRADE
    for n in ast.walk(scope):
        if isinstance(n, ast.Return) and n.value is not None \
                and base in ast.unparse(n.value):
            return STOP
    return ANNOTATE


def entry_points(modules) -> dict:
    """For each module that calls a guard: is it runnable, and does anything run it?

    A guard reached only from a module nobody invokes is protected by nothing,
    whatever its call graph says. `__main__` makes a module runnable BY HAND;
    a workflow or runbook reference is what makes it run without one.
    """
    wf_text = ''
    for d in ('.github', 'docs'):
        base = ROOT / d
        if not base.exists():
            continue
        for f in base.rglob('*'):
            if f.is_file() and f.suffix in ('.yml', '.yaml', '.md'):
                wf_text += f.read_text(errors='replace')
    for extra in ('COMMANDS.md',):
        if (ROOT / extra).exists():
            wf_text += (ROOT / extra).read_text(errors='replace')
    out = {}
    for m in sorted(modules):
        src = (ROOT / m).read_text(errors='replace') if (ROOT / m).exists() else ''
        stem = m[:-3] if m.endswith('.py') else m
        out[m] = {'has_main': '__main__' in src,
                  'referenced_outside_python': stem in wf_text
                  or pathlib.Path(m).stem in wf_text}
    return out


def census() -> dict:
    defs = definitions()
    sites = call_sites(defs)
    rows = []
    for g in sorted(defs):
        all_sites = sites.get(g, [])
        for _d in defs[g]:
            if len(defs[g]) > 1:
                # One row per DEFINITION. A site that could not be resolved to
                # a file is attributed to neither rather than to both.
                s = [x for x in all_sites if x.get('resolves_to') == _d['file']]
            else:
                s = all_sites
            rows.append(_row(g, [_d], s, len(defs[g])))
    return {'spec_version': 'nfl-guard-reachability-2',
            'n_guards': len(rows), 'rows': rows}


def _row(g, dfs_for_this, s, n_defs_of_name) -> dict:
        defs = {g: dfs_for_this}
        own = {d['file'] for d in defs[g]}
        prod = [x for x in s if x['kind'] == 'prod']
        ext = [x for x in prod if x['file'] not in own]
        raises = any(d['raises'] for d in defs[g])
        returns = any(d['returns_a_value'] for d in defs[g])
        effects = sorted({x['effect'] for x in ext}) or \
            sorted({x['effect'] for x in prod})
        # A GUARD THAT RAISES ON FAILURE IS A STOP, whatever the caller does
        # with the return value.
        #
        # The first version of this rule only said so when the guard NEVER
        # returned a value, and it therefore misclassified assert_graded_row --
        # which raises AnonymousZero on failure and returns the provenance
        # block on success -- as NOTHING, because grade_projections calls it as
        # a bare statement. That is exactly backwards: the raise IS the stop,
        # and the returned value is the success value, so discarding it costs
        # nothing. Only a guard that can FAIL WITHOUT RAISING needs its caller
        # to branch, and those are the DEF-065 population.
        if raises and prod:
            effects = [STOP]
        # A NAME IS NOT AN IDENTITY WHEN TWO MODULES DEFINE IT. There are two
        # `assert_publishable`, and they classify DIFFERENTLY: the
        # current_season_team_volume one stops a forecast, the layers one is
        # advisory. A table keyed on the bare name would give both the same
        # answer and one of them would be a lie. So a qualified
        # `module::guard` key wins, and the bare name remains the default for
        # the single-definition majority.
        _qual = [f"{d['file']}::{g}" for d in sorted(
            defs[g], key=lambda d: d['file'])]
        cls, why = ('NOT_ESTABLISHED', '')
        for _k in _qual + [g]:
            if _k in CLASSIFICATION:
                cls, why = CLASSIFICATION[_k]
                break
        proof = ''
        for _k in _qual + [g]:
            if _k in LOAD_BEARING_PROOFS:
                proof = LOAD_BEARING_PROOFS[_k]
                break
        caller_mods = sorted({x['file'] for x in prod})
        eps = entry_points(caller_mods)
        det = {}
        for t in ({proof} if proof else set()):
            det[t] = TEST_DETERMINISM.get(t, ('NOT_ESTABLISHED', ''))[0]
        return {
            'guard': g,
            'protects': defs[g][0].get('protects', ''),
            'defined_in': defs[g][0]['file'],
            'line': defs[g][0]['lineno'],
            'n_definitions': len(defs[g]),
            'fails_by': ('RAISE' if raises and not returns
                         else 'RETURN' if returns and not raises
                         else 'RAISE_OR_RETURN' if raises else 'NEITHER'),
            'callers_prod': len(prod),
            'callers_prod_external': len(ext),
            'callers_test': len([x for x in s if x['kind'] == 'test']),
            'callers_research': len([x for x in s if x['kind'] == 'research']),
            'effect_on_failure': effects or ['NO_PRODUCTION_CALLER'],
            'reachability': ('NO_CALLER_AT_ALL' if not s else
                             'NO_PROD_CALLER' if not prod else
                             'INTERNAL_ONLY' if not ext else
                             'EXTERNALLY_CALLED'),
            'caller_modules': caller_mods,
            'caller_entry_points': eps,
            'runnable_caller': any(v['has_main'] for v in eps.values()),
            'caller_referenced_outside_python':
                any(v['referenced_outside_python'] for v in eps.values()),
            'direct_test_coverage': bool([x for x in s if x['kind'] == 'test']),
            'load_bearing_proof': proof or 'NONE',
            'load_bearing_proof_determinism': det,
            'classification': cls,
            'classification_reason': why,
            'prod_sites': [f"{x['file']}:{x['lineno']}:{x['effect']}"
                           for x in prod],
            'n_definitions_of_this_name': n_defs_of_name,
        }


def markdown(c) -> str:
    """The census as a table. Emitted BY THE TOOL so the artifact cannot drift.

    The first version of GUARD_CENSUS.md was generated by a heredoc in a shell
    command, which meant the committed table and the tool were two things that
    had to be kept in step by hand -- the same class of defect as a count
    written into prose.
    """
    rows = c['rows']
    tally = collections.Counter(r['reachability'] for r in rows)
    eff = collections.Counter(x.split(':')[0]
                              for r in rows for x in r['effect_on_failure'])
    cls = collections.Counter(r['classification'] for r in rows)
    L = [f"# Guard census — {c['n_guards']} guards", '',
         'Emitted by `nfl/tools/guard_reachability.py --md`. Re-run it rather',
         'than trusting these counts.', '',
         '`classification`, `load_bearing_proof` and test determinism are',
         'DECLARED in the tool, defaulting to `NOT_ESTABLISHED`: each is a',
         'judgement, and a tool that guessed them would manufacture the',
         'confidence this census exists to strip out.', '',
         '| reachability | n | effect on failure | n | classification | n |',
         '|---|---|---|---|---|---|']
    rk = ['NO_CALLER_AT_ALL', 'NO_PROD_CALLER', 'INTERNAL_ONLY',
          'EXTERNALLY_CALLED']
    ek = [k for k, _ in eff.most_common()]
    ck = [k for k, _ in cls.most_common()]
    for i in range(max(len(rk), len(ek), len(ck))):
        a = f'{rk[i]} | {tally[rk[i]]}' if i < len(rk) else ' | '
        b = f'{ek[i]} | {eff[ek[i]]}' if i < len(ek) else ' | '
        d = f'{ck[i]} | {cls[ck[i]]}' if i < len(ck) else ' | '
        L.append(f'| {a} | {b} | {d} |')
    L += ['', '## Guards with a load-bearing proof', '',
          'A seeded bad state, the guard reporting FAIL, and the protected',
          'action demonstrably not happening.', '',
          '| guard | protects | proof | determinism |', '|---|---|---|---|']
    for r in rows:
        if r['load_bearing_proof'] != 'NONE':
            det = ', '.join(sorted(set(
                r['load_bearing_proof_determinism'].values()))) or '—'
            L.append(f"| `{r['guard']}` | {r['protects'][:58]} | "
                     f"`{r['load_bearing_proof'].split('/')[-1]}` | {det} |")
    L += ['', '## Every guard', '',
          '| guard | effect | reach | direct test | proof | class | caller '
          'runnable | caller in a workflow |',
          '|---|---|---|---|---|---|---|---|']
    for r in sorted(rows, key=lambda r: (r['classification'] != 'LOAD_BEARING',
                                         r['reachability'], r['guard'])):
        L.append(
            f"| `{r['guard']}` "
            f"| {','.join(x.split(':')[0] for x in r['effect_on_failure'])} "
            f"| {r['reachability']} "
            f"| {'yes' if r['direct_test_coverage'] else '**no**'} "
            f"| {'yes' if r['load_bearing_proof'] != 'NONE' else '—'} "
            f"| {r['classification']} "
            f"| {'yes' if r['runnable_caller'] else '—'} "
            f"| {'yes' if r['caller_referenced_outside_python'] else '**no**'} |")
    n_wf = sum(1 for r in rows if r['caller_referenced_outside_python'])
    L += ['', '## The column that decides VERIFIED', '',
          f'Only **{n_wf} of {len(rows)}** guards have a caller referenced by '
          'any workflow,',
          'runbook or doc. A guard reached only from a module nobody invokes is',
          'protected by nothing, whatever its call graph says.']
    return '\n'.join(L) + '\n'


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    c = census()
    if '--json' in argv:
        print(json.dumps(c, indent=1))
        return 0
    if '--md' in argv:
        print(markdown(c), end='')
        return 0
    rows = c['rows']
    print(f"{c['n_guards']} guards\n")
    tally = collections.Counter(r['reachability'] for r in rows)
    for k in ('NO_CALLER_AT_ALL', 'NO_PROD_CALLER', 'INTERNAL_ONLY',
              'EXTERNALLY_CALLED'):
        print(f'  {k:20s} {tally[k]:3d}')
    print()
    eff = collections.Counter(e for r in rows for e in r['effect_on_failure'])
    print('effect on failure, across production call sites:')
    for k, v in eff.most_common():
        print(f'  {k:22s} {v:3d}')
    print()
    print(f"{'guard':40s} {'fails_by':16s} {'reach':18s} effect  test")
    for r in sorted(rows, key=lambda r: (r['reachability'], r['guard'])):
        print(f"{r['guard']:40s} {r['fails_by']:16s} "
              f"{r['reachability']:18s} "
              f"{','.join(r['effect_on_failure']):22s} {r['callers_test']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
