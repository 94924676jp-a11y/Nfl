"""SHADOW (research only, writes only to scratch): week-4 early Classic production projection, paired.
arm INCUMBENT: proj_v1 unmodified.  arm DEPTHFIX: identical, except depth_shares() receives a position map that
also covers players absent from the 2026-only rosters (forward_chain.positions_for_chain's usage inference).
Panel is truncated to 2026 weeks < SLATE_WEEK so no week-4 usage enters either arm."""
import json, os, pathlib, sys, copy
SCR = pathlib.Path('/tmp/claude-0/trackb/l4')
arm = sys.argv[1]
from nfl.tools import player_prior as PP, proj_v1 as PV, role_state as RS, forward_chain as FC
REPO = pathlib.Path('.').resolve()
STATE = REPO / 'nfl/dfs/salaries/DK_2026W4_EARLY_STATE.json'
state = json.loads(STATE.read_text())
wk = int(state['week'])
o = PP.load_panel()
panel = o.value
dropped = 0
for g, ss in panel['players'].items():
    cur = ss.get('2026') or {}
    for w in [w for w in cur if int(w) >= wk]:
        del cur[w]; dropped += 1
for c, ss in panel['teams'].items():
    cur = ss.get('2026') or {}
    for w in [w for w in cur if int(w) >= wk]:
        del cur[w]
PP.load_panel = lambda: o
roster = PP.position_index()
if arm == 'DEPTHFIX':
    pos_map, inferred = FC.positions_for_chain(panel, roster)
    aug = dict(roster)
    for (g, s), p in sorted(pos_map.items(), key=lambda x: x[0][1]):
        if g not in roster:
            aug[g] = p
    _ds = PV.depth_shares
    PV.depth_shares = lambda panel_, pos_of, through=None: _ds(panel_, aug, through=through)
RS.POST, RS.OUT = STATE, SCR / f'ROLE_{arm}.json'
rs = RS.run(); assert rs.state.value == 'PASS', rs
PV.POST, PV.OUT, PV.ROLE, PV.SLATE_WEEK = STATE, SCR / f'PROJ_{arm}.json', SCR / f'ROLE_{arm}.json', wk
PV.MARKET_ARM = 'FOOTBALL_ONLY'
rc = PV.main()
print(arm, 'rc', rc, 'dropped player-weeks', dropped)
