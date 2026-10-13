"""PORT-D3 stage attribution (PREREG @b1945cd5): the SAME production selector (SPF.run -> build_contests, same caps/ladder/
polish, GLOBAL overlap) on (b) the top-5,946 of U by persistence h (ties: mean) or (c) the union of production pool and
(b). Arm (a) is the production FINAL_CV1 portfolio itself. Run in the corrected overlay. usage: d3_stage.py B|C"""
import json, os, pathlib, sys, time
import numpy as np
sys.path.insert(0, '.')
os.environ['NFL_SHOWDOWN_OVERLAP_POLICY'] = 'GLOBAL'
from nfl.tools import showdown_portfolio as SPF, showdown_to_portfolio as S
from sportsplatform.governance.outcome import Outcome
arm = sys.argv[1]
B = pathlib.Path('nfl/dfs/salaries/showdown_buf_lar').resolve()
E = 'nfl/dfs/salaries/raw/showdown_buf_lar_2026W5/DKEntries_BUF_LAR_SHOWDOWN_2026W5.81b504dbc36395c4.csv'
src = B / 'FINAL_CV1'
out = B / f'SHADOW_D3_ARM_{arm}'
assert not out.exists(), out
_U = np.load('/tmp/claude-0/mnf_post/d3_universe.npz')
U = {k: _U[k] for k in ('L', 'H', 'MEAN', 'keys')}   # load each member ONCE (npz members decompress on every access)
keys = [str(k) for k in U['keys']]
order = np.lexsort((-U['MEAN'], -U['H']))[:5946]
LL = U['L']
top = [{'captain': keys[int(LL[i, 0])], 'flex': sorted(keys[int(j)] for j in LL[i, 1:]), 'n_worlds_optimal': 0}
       for i in order]
orig_gen, orig_forced = S.near_optimal_candidates, SPF.forced_captain_candidates
rec = {'arm': arm, 'prereg': 'PREREG_PORT_D3_CANDIDATE_RECALL.md @b1945cd5', 'enriched_n': len(top),
       'enriched_h_min': int(U['H'][order].min()), 'enriched_h_median': float(np.median(U['H'][order]))}
def gen(slate, absent, draws, **k):
    if arm == 'B':
        return Outcome.ok('D3_ENRICHED_POOL', top, f'{len(top)} top-persistence lineups')
    o = orig_gen(slate, absent, draws, **k)
    have = {(r['captain'], tuple(sorted(r['flex']))) for r in o.value}
    extra = [r for r in top if (r['captain'], tuple(r['flex'])) not in have]
    rec['union_added'] = len(extra)
    return Outcome.ok(o.code, list(o.value) + extra, o.detail)
S.near_optimal_candidates = gen
if arm == 'B':
    SPF.forced_captain_candidates = lambda rows: ({}, {'state': 'DISABLED_FOR_D3_ARM_B'})
scen = json.loads((src / 'SCENARIO.json').read_text())
t = time.time()
pf = SPF.run(E, src / 'SHOWDOWN_BUF_LAR_2026W5_DRAWS.json', out, 'SHOWDOWN_BUF_LAR', inactives=scen['absent_in_state'],
             proj_path=src / 'SHOWDOWN_BUF_LAR_2026W5_PROJ.json', state_path=src / 'SHOWDOWN_BUF_LAR_2026W5_STATE.json')
rec['selector_seconds'] = round(time.time() - t, 1)
rec['portfolio'] = f'{pf.state.value} {pf.code} {pf.detail[:400]}'
(out / 'D3_ARM_LOG.json').write_text(json.dumps(rec, indent=1))
print(json.dumps(rec))
