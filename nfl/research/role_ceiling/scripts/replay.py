"""Replay one stored pregame classic state through the CURRENT engine with a point-in-time panel (2026 weeks >= the
slate week removed), under a research arm. Writes only to OUT (inside the w5 worktree's ignored runs/ dir)."""
import json, pathlib, shutil, sys, os
W = pathlib.Path(os.environ.get('REPO', '/home/user/p0work/nfl-w5')); sys.path.insert(0, str(W)); sys.path.insert(0, str(pathlib.Path(__file__).parent))
state_p, out, arm = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), sys.argv[3]
out.mkdir(parents=True, exist_ok=True); shutil.copy(state_p, out / 'STATE.json')
wk = int(json.loads(state_p.read_text())['week'])
from nfl.tools import player_prior as PP
_orig = PP.load_panel
def _pit():
    o = _orig(); p = o.value
    for g, ss in p['players'].items():
        if '2026' in ss: ss['2026'] = {w: v for w, v in ss['2026'].items() if int(w) < wk}
    for c, ss in p['teams'].items():
        if '2026' in ss: ss['2026'] = {w: v for w, v in ss['2026'].items() if int(w) < wk}
    return o
PP.load_panel = _pit
from nfl.tools import classic_slate_run as CR, role_state as RS, proj_v1 as PV
import tie_arms; tie_arms.apply(arm)
CR.paths = lambda s: {'state': out / 'STATE.json', 'proj': out / 'PROJ.json', 'draws': out / 'DRAWS.json', 'worlds': out / 'WORLDS.npz'}
RS.OUT = PV.ROLE = out / 'ROLE_STATE.json'
o = CR.run('replay', n_sims=int(sys.argv[4]) if len(sys.argv) > 4 else 1000)
print(arm, o.state.value, o.code, o.detail)
(out / 'RUN_OUTCOME.json').write_text(json.dumps({'arm': arm, 'week': wk, 'state': o.state.value, 'code': o.code, 'detail': o.detail}, default=str))
