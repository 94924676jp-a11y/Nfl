"""Measure: collected test modules whose test functions FG counts as having zero checks, while they call a
module-local check helper FG does not recognise (ok/ck/expect/_check/...). Read-only, at the worktree commit."""
import ast, glob, json, re, sys, collections
sys.path[:0] = ['/home/user/p0work/pylib', '/home/user/nfl-phase1']
from nfl.tools import floor_guard as FG
R = '/home/user/nfl-phase1'
rows = []
for p in sorted(glob.glob(R + '/nfl/tests/test_*.py')):
    rel = p[len(R) + 1:]
    src = open(p).read()
    t = FG._tests_in(src) or {}
    tree = ast.parse(src)
    defs = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    calls = collections.Counter(FG._callee(c) for c in ast.walk(tree) if isinstance(c, ast.Call))
    helper = [h for h in ('ok', 'ck', 'expect', '_check', 'check_', 'assert_', '_ok') if h in defs and calls[h] > 1]
    n_fn = len(t); zero = sum(1 for f in t.values() if f['n_checks'] == 0)
    rows.append({'path': rel, 'n_test_fns': n_fn, 'n_zero_check_fns': zero, 'unrecognised_helpers': helper,
                 'helper_calls': {h: calls[h] for h in helper}})
blind = [r for r in rows if r['unrecognised_helpers'] and r['n_test_fns'] and r['n_zero_check_fns'] == r['n_test_fns']]
json.dump({'modules': len(rows), 'blind_modules': blind}, open('/tmp/claude-0/review3/helper_coverage.json', 'w'), indent=1)
print('collected test modules', len(rows), '; every test fn reads 0 checks and module uses an unrecognised helper:', len(blind))
print('test fns in those modules', sum(r['n_test_fns'] for r in blind), '; helper calls', sum(sum(r['helper_calls'].values()) for r in blind))
for r in blind[:60]: print(' ', r['path'], r['n_test_fns'], r['helper_calls'])
