"""Research build of the TB@DAL Showdown portfolio with a different PLAYER exposure cap. Production untouched:
the cap is changed only on this process's copy of showdown_portfolio.LADDER."""
import json, sys, pathlib
sys.path.insert(0, '/home/user/nfl')
from nfl.tools import showdown_portfolio as SPF
cap = float(sys.argv[1]); out = pathlib.Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
capt = 0.30 if cap < 1.0 else 1.0
SPF.LADDER = tuple({'level': i, 'overlap': SPF.S.MAX_OVERLAP + (1 if i else 0), 'player': cap, 'captain': capt} for i in range(2))
S = pathlib.Path('/home/user/nfl/nfl/dfs/salaries/showdown_tb_dal')
pf = SPF.run('/home/user/nfl/nfl/dfs/salaries/raw/showdown_tb_dal_2026W5/DKEntries_TB_DAL_SHOWDOWN_2026W5.5d559e413e680cae.csv',
             S/'OFFICIAL/SHOWDOWN_TB_DAL_2026W5_DRAWS.json', out, 'SHOWDOWN_TB_DAL',
             inactives=json.loads((S/'OFFICIAL_ELIGIBILITY_FIX_R1/BLOCKLIST.json').read_text()),
             proj_path=S/'OFFICIAL/SHOWDOWN_TB_DAL_2026W5_PROJ.json', state_path=S/'OFFICIAL/SHOWDOWN_TB_DAL_2026W5_STATE.json')
print('CAP', cap, pf.state.value, pf.code, pf.detail)
