"""The census tool's own regression test. It has been wrong five times.

`nfl/tools/guard_reachability.py` produces the evidence this audit acts on, and
it had no test. Every one of its five corrections so far was a FALSE ACCUSATION
against working code, found by reading the code rather than by the tool:

  1. RAISE vs RETURN     a guard that raises on failure is a STOP even when
                         called as a bare statement -- the raise IS the stop.
                         Mislabelled assert_graded_row as NOTHING.
  2. VERDICT REGISTRY    an Outcome mapped through verdict.from_outcome into a
                         required gate is enforced, though the calling line only
                         stores it. Mislabelled five run_chain guards ANNOTATE.
  3. TERNARY             `x = (a if guard.state is PASS else b)` is a branch.
                         ast.If alone missed it and mislabelled assert_publishable.
  4. ORDER               checking the ternary first stole guards that genuinely
                         stop; STOP fell 36 -> 31 until stopping evidence won.
  5. TUPLE UNPACK        `legal, why = guard(...)` made the bound name the string
                         'legal, why', matching no test. Mislabelled
                         assert_roster_legal, which stops the DFS optimizer.

A census that over-reports is not erring on the safe side: it spends the
reader's trust, and an audit whose instrument is untrusted produces nothing. So
each correction is pinned here against a synthetic module, because a fixture
built for the property is the only way to test a classifier's edges without
waiting for the codebase to grow one.
"""
import importlib.util
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_spec = importlib.util.spec_from_file_location(
    'gr', _REPO / 'nfl/tools/guard_reachability.py')
GR = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(GR)

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


import ast  # noqa: E402


def _effect_of(src: str, guard='assert_thing') -> str:
    """Classify the single call site in `src`, the way census() does."""
    t = ast.parse(src)
    parent = {}
    for node in ast.walk(t):
        for ch in ast.iter_child_nodes(node):
            parent[ch] = node
    for n in ast.walk(t):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        nm = (f.attr if isinstance(f, ast.Attribute)
              else f.id if isinstance(f, ast.Name) else None)
        if nm != guard:
            continue
        cur = n
        while cur in parent and not isinstance(parent[cur], ast.stmt):
            cur = parent[cur]
        stmt = parent.get(cur)
        target = None
        if isinstance(stmt, ast.Assign):
            tg = stmt.targets[0]
            if isinstance(tg, ast.Tuple):
                target = [e.id for e in tg.elts if isinstance(e, ast.Name)]
            else:
                target = (tg.id if isinstance(tg, ast.Name)
                          else ast.unparse(tg))
        eff = GR._effect(stmt, n, target)
        if eff is None:
            eff = GR._traced_effect(t, stmt, target)
        gate = GR._registered_gate(t, stmt, target)
        if gate and eff in (GR.ANNOTATE, GR.NOTHING, None):
            eff = f'{GR.VERDICT}:{gate}'
        return eff
    return 'NO_CALL_FOUND'


def test_a_branch_that_returns_is_a_stop():
    print('\n[1] the baseline: if ... return')
    e = _effect_of('''
def caller():
    o = assert_thing(x)
    if o.state is not PASS:
        return o
    go()
''')
    check('if/return is STOP', e == GR.STOP, str(e))
    e2 = _effect_of('''
def caller():
    o = assert_thing(x)
    if o.state is not PASS:
        log(o)
    go()
''')
    check('if without return is DOWNGRADE', e2 == GR.DOWNGRADE, str(e2))
    e3 = _effect_of('''
def caller():
    o = assert_thing(x)
    report['gate'] = o.code
    go()
''')
    check('stored and never branched on is ANNOTATE', e3 == GR.ANNOTATE,
          str(e3))
    e4 = _effect_of('''
def caller():
    assert_thing(x)
    go()
''')
    check('a bare call with no raise is NOTHING', e4 == GR.NOTHING, str(e4))


def test_correction_3_a_ternary_is_a_branch():
    print('\n[2] correction 3: the conditional expression')
    e = _effect_of('''
def caller():
    o = assert_thing(x)
    report['gate'] = o.code
    verified = ({'a': o} if o.state is PASS else {})
    downstream(verified_inputs=verified)
''')
    check('a ternary on the result is DOWNGRADE, not ANNOTATE',
          e == GR.DOWNGRADE, str(e))


def test_correction_4_stopping_evidence_wins_over_a_ternary():
    print('\n[3] correction 4: ordering')
    e = _effect_of('''
def caller():
    o = assert_thing(x)
    tag = ('bad' if o.state is not PASS else 'ok')
    if o.state is not PASS:
        return o
    go(tag)
''')
    check('a guard with BOTH a ternary and if/return is STOP',
          e == GR.STOP,
          f'{e} -- checking the ternary first dropped STOP from 36 to 31')


def test_correction_5_tuple_unpacking():
    print('\n[4] correction 5: (ok, why) = guard(...)')
    e = _effect_of('''
def caller():
    legal, why = assert_thing(a, b)
    if not legal:
        return
    go()
''')
    check('a tuple-unpacked result branched on is STOP', e == GR.STOP,
          f'{e} -- this is the DFS optimizer rejecting an illegal roster')
    e2 = _effect_of('''
def caller():
    legal, why = assert_thing(a, b)
    report['why'] = why
    go()
''')
    check('and tuple-unpacked with no branch is still ANNOTATE',
          e2 == GR.ANNOTATE, str(e2))


def test_correction_2_the_verdict_registry():
    print('\n[5] correction 2: registered through from_outcome')
    e = _effect_of('''
def caller():
    o = assert_thing(x)
    L['thing'] = {'code': o.code}
    G['INACTIVE_APPLICATION'] = V.from_outcome(o)
''')
    check('a registered Outcome is VERDICT_REGISTERED with its gate',
          e == 'VERDICT_REGISTERED:INACTIVE_APPLICATION', str(e))
    e2 = _effect_of('''
def caller():
    o = assert_thing(x)
    states.append(o)
    G['OPPORTUNITY_CONSERVATION'] = aggregate(states)
''')
    check('and one append hop is followed',
          e2 == 'VERDICT_REGISTERED:OPPORTUNITY_CONSERVATION', str(e2))


def test_correction_1_a_raising_guard_stops_even_when_bare():
    print('\n[6] correction 1: raise is the stop')
    with tempfile.TemporaryDirectory() as tmp:
        d = pathlib.Path(tmp)
        (d / 'g.py').write_text(
            'def assert_thing(x):\n'
            '    if not x:\n'
            '        raise RuntimeError("no")\n'
            '    return {"ok": True}\n')
        t = ast.parse((d / 'g.py').read_text())
        fn = [n for n in ast.walk(t) if isinstance(n, ast.FunctionDef)][0]
        raises = any(isinstance(x, ast.Raise) for x in ast.walk(fn))
        returns = any(isinstance(x, ast.Return) and x.value is not None
                      for x in ast.walk(fn))
        check('the fixture both raises and returns a value',
              raises and returns, f'raises={raises} returns={returns}')
        # census() forces STOP for any raising guard with a production caller.
        src = GR.pathlib.Path(_REPO / 'nfl/tools/guard_reachability.py').read_text()
        check('census forces STOP on `raises and prod`, not `raises and not returns`',
              'if raises and prod:' in src,
              'the narrower rule mislabelled assert_graded_row as NOTHING')


def test_alias_resolution_splits_same_named_guards():
    print('\n[7] two guards may share a name')
    src = '''
from nfl.production.nonqb import layers as LY
from nfl.production.nonqb import current_season_team_volume as TV
'''
    t = ast.parse(src)
    al = GR.alias_map(t)
    check('LY resolves to layers.py',
          al.get('LY') == 'nfl/production/nonqb/layers.py', str(al.get('LY')))
    check('TV resolves to current_season_team_volume.py',
          al.get('TV') == 'nfl/production/nonqb/current_season_team_volume.py',
          str(al.get('TV')))
    c = GR.census()
    pub = [r for r in c['rows'] if r['guard'] == 'assert_publishable']
    check('assert_publishable is TWO rows, not one merged row',
          len(pub) == 2, f'{len(pub)} row(s)')
    check('and they carry different defining modules',
          len({r['defined_in'] for r in pub}) == 2,
          str(sorted(r['defined_in'].split('/')[-1] for r in pub)))
    comp = [r for r in c['rows'] if r['guard'] == 'assert_complete']
    check('assert_complete likewise', len(comp) == 2, f'{len(comp)} row(s)')
    check('and the uncalled one is no longer hidden behind the wired one',
          {r['reachability'] for r in comp}
          == {'EXTERNALLY_CALLED', 'NO_CALLER_AT_ALL'},
          str({r['defined_in'].split('/')[-1]: r['reachability']
               for r in comp}))


def main():
    print(__doc__.strip().splitlines()[0])
    test_a_branch_that_returns_is_a_stop()
    test_correction_3_a_ternary_is_a_branch()
    test_correction_4_stopping_evidence_wins_over_a_ternary()
    test_correction_5_tuple_unpacking()
    test_correction_2_the_verdict_registry()
    test_correction_1_a_raising_guard_stops_even_when_bare()
    test_alias_resolution_splits_same_named_guards()
    print(f'\n{PASSED} passed, {FAILED} failed')
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())
