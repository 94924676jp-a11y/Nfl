"""Run classic_slate_run on the RESEARCH state in the isolated W5 worktree, writing only to OUT. Research only."""
import json, pathlib, shutil, sys
W = pathlib.Path('/home/user/p0work/nfl-w5'); sys.path.insert(0, str(W))
from nfl.tools import classic_slate_run as CR
from nfl.tools import role_state as RS
state, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
shutil.copy(state, out / 'STATE.json')
CR.paths = lambda s: {'state': out / 'STATE.json', 'proj': out / 'PROJ.json', 'draws': out / 'DRAWS.json',
                      'worlds': out / 'WORLDS.npz'}
from nfl.tools import proj_v1 as PV
RS.OUT = PV.ROLE = out / 'ROLE_STATE.json'
import os
if os.environ.get('ARM') == 'TIE1':
    sys.path.insert(0, str(pathlib.Path(__file__).parent)); import tie_patch  # noqa: F401
o = CR.run('2026W5', n_sims=int(sys.argv[3]) if len(sys.argv) > 3 else 2000)
print(o.state.value, o.code, o.detail)
(out / 'RUN_OUTCOME.json').write_text(json.dumps({'state': o.state.value, 'code': o.code, 'detail': o.detail,
                                                 'evidence': o.evidence}, indent=1, default=str))
