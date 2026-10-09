"""Research build of the TB@DAL Showdown portfolio on a given DRAWS.json. Worktree code; production LADDER unchanged.
argv: draws_path out_dir"""
import json, sys, pathlib, time
REPO = pathlib.Path(__file__).resolve().parents[4]; sys.path.insert(0, str(REPO))
from nfl.tools import showdown_portfolio as SPF
draws, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
S = REPO / 'nfl/dfs/salaries/showdown_tb_dal'
t = time.time()
pf = SPF.run(str(REPO / 'nfl/dfs/salaries/raw/showdown_tb_dal_2026W5/DKEntries_TB_DAL_SHOWDOWN_2026W5.5d559e413e680cae.csv'),
             draws, out, 'SHOWDOWN_TB_DAL',
             inactives=json.loads((S / 'OFFICIAL_ELIGIBILITY_FIX_R1/BLOCKLIST.json').read_text()),
             proj_path=S / 'OFFICIAL/SHOWDOWN_TB_DAL_2026W5_PROJ.json', state_path=S / 'OFFICIAL/SHOWDOWN_TB_DAL_2026W5_STATE.json')
print('DONE', pf.state.value, pf.code, pf.detail, f'{time.time()-t:.0f}s')
