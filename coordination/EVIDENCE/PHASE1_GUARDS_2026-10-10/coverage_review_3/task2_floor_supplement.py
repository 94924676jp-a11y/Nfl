"""Supplementary floor_guard probes (not part of the 20), each reproducing a pattern observed in Task 1."""
import json, sys, textwrap, traceback
sys.path[:0] = ['/home/user/p0work/pylib', '/home/user/nfl-phase1', '/tmp/claude-0/review3']
import task2_floor as T          # reuses build(); re-running its module body re-runs the 20 (idempotent)
from nfl.tools import floor_guard as FG
D = textwrap.dedent
OK_MOD = D('''\
    PASSED = FAILED = 0


    def ok(cond, msg):
        global PASSED, FAILED
        if cond:
            PASSED += 1
        else:
            FAILED += 1
        print(('PASS ' if cond else 'FAIL ') + msg)


    def test_flags():
        flags = {'a': True, 'b': True}
        ok(flags['a'], 'a is set')
        ok(flags['b'], 'b is set')


    def test_defects():
        kinds = {'x': 'SHARE'}
        for k in kinds:
            ok(kinds[k] == 'SHARE', f'{k} names the defect')


    def test_equivalence():
        diffs = {'spec_version': 3}
        declared = {'spec_version'}
        real = {k: v for k, v in diffs.items() if k not in declared}
        ok(not real, 'no undeclared difference')


    def test_share():
        share = 0.7
        assert share > 0.5
    ''')
RES = json.dumps({'verdicts': [{'name': 'a', 'state': 'PASS'}, {'name': 'b', 'state': 'FAIL'}]}, indent=1) + '\n'
T.BASE['nfl/tests/test_okmod.py'] = OK_MOD
T.BASE['results/run_status.json'] = RES
X = [
    ('X1_ok_helper_never_fails', True, "module-local ok() helper stops counting failures (helper named ok, not check)",
     T.sub('nfl/tests/test_okmod.py', '    if cond:\n        PASSED += 1\n    else:\n        FAILED += 1\n', '    PASSED += 1\n')),
    ('X2_ok_call_deleted', True, 'an ok(flag, msg) check with no comparison deleted from a test',
     T.sub('nfl/tests/test_okmod.py', "    ok(flags['b'], 'b is set')\n", '')),
    ('X3_eq_loosened_masked', True, 'Eq check loosened to a subset test while another Eq check is added (Task 1 638af4f6)',
     T.sub('nfl/tests/test_okmod.py', "        ok(kinds[k] == 'SHARE', f'{k} names the defect')\n",
           "        ok({kinds[k]} <= {'SHARE', 'RATE'}, f'{k} names a known defect')\n"
           "    ok(kinds['x'] == 'SHARE', 'x is the share defect')\n")),
    ('X4_exclusion_set_widened', True, 'equivalence test: declared-difference set widened (out of spec text; Task 1 a62d8b82)',
     T.sub('nfl/tests/test_okmod.py', "declared = {'spec_version'}", "declared = {'spec_version', 'axes.availability'}")),
    ('X5_json_list_insert_shift', False, 'a new PASS verdict inserted before an unchanged FAIL (Task 1 4bf829c3 index shift)',
     T.write('results/run_status.json', json.dumps({'verdicts': [{'name': 'a', 'state': 'PASS'}, {'name': 'a2', 'state': 'PASS'},
                                                                 {'name': 'b', 'state': 'FAIL'}]}, indent=1) + '\n')),
    ('X6_or_zero_operand', False, 'assert share > 0.5 -> assert (share or 0) > 0.5: same operator and bound (Task 1 54c782f2)',
     T.sub('nfl/tests/test_okmod.py', 'assert share > 0.5', 'assert (share or 0) > 0.5')),
]
out = []
for name, expect, why, change in X:
    rec = {'case': name, 'should_report': expect, 'what': why}
    try:
        p = T.build(name, change)
        rep = FG.run(str(p), 'HEAD~1', 'HEAD')
        rf = [f for f in rep['findings'] if f['severity'] in ('high', 'medium')]
        rec['findings'] = [{k: f[k] for k in ('rule', 'severity', 'path', 'detail')} for f in rep['findings']]
        rec['outcome'] = ('TP' if rf else 'MISS') if expect else ('FALSE_POSITIVE' if rf else 'TN')
    except Exception as e:
        rec['outcome'] = 'CRASH'; rec['error'] = f'{type(e).__name__}: {e}'; rec['tb'] = traceback.format_exc()
    out.append(rec)
json.dump(out, open('/tmp/claude-0/review3/task2_floor_supplement_results.json', 'w'), indent=1)
print('---- supplementary')
for r in out:
    print(f"{r['case']:28s} expect={'REPORT' if r['should_report'] else 'quiet '} -> {r['outcome']:15s}",
          '; '.join(f"{f['rule']}/{f['severity']}" for f in r.get('findings', [])) or r.get('error', ''))
