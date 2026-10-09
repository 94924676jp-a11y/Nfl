import json, sys, pathlib, hashlib
sys.path.insert(0, '/home/user/nfl')
from nfl.tools import showdown_tonight as T, showdown_portfolio as SPF, roster_eligibility as E
R = pathlib.Path('/home/user/nfl'); S = R/'nfl/dfs/salaries/showdown_tb_dal'; RAW = R/'nfl/dfs/salaries/raw/showdown_tb_dal_2026W5'
export = RAW/'DKEntries_TB_DAL_SHOWDOWN_2026W5.5d559e413e680cae.csv'
scen = json.loads((S/'OFFICIAL/SCENARIO.json').read_text())
blocked = T.roster_blocked(export, 'TB_DAL_2026W5', R/'nfl/vintage/weekly_rosters.dba8eeff1f9c0878.raw.csv.gz',
                           json.loads((RAW/'ROTOWIRE_INACTIVES_TB_DAL_2026W5.json').read_text()),
                           json.loads((S/'OFFICIAL_ELIGIBILITY_FIX_R1/TRANSACTIONS_OWNER_RELAYED.json').read_text()),
                           json.loads((S/'OFFICIAL_ELIGIBILITY_FIX_R1/ELEVATIONS_OWNER_RELAYED.json').read_text()))
absent = sorted(set(scen['absent_in_state']) | set(blocked))
pool = {n for (n, c) in E.dk_pool(export)}
r1 = set(json.loads((S/'OFFICIAL_ELIGIBILITY_FIX_R1/BLOCKLIST.json').read_text()))
print('blocked', len(blocked), 'absent_union', len(absent), 'R1 blocklist', len(r1))
print('in DK pool: union == R1 ?', (set(absent) & pool) == (r1 & pool), sorted((set(absent) ^ r1) & pool))
out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
pf = SPF.run(export, S/'OFFICIAL/SHOWDOWN_TB_DAL_2026W5_DRAWS.json', out, 'SHOWDOWN_TB_DAL', inactives=absent,
             proj_path=S/'OFFICIAL/SHOWDOWN_TB_DAL_2026W5_PROJ.json', state_path=S/'OFFICIAL/SHOWDOWN_TB_DAL_2026W5_STATE.json')
print(pf.state.value, pf.code, pf.detail)
got = hashlib.sha256((out/'SHOWDOWN_TB_DAL_DK_UPLOAD.csv').read_bytes()).hexdigest()
want = hashlib.sha256((S/'OFFICIAL_ELIGIBILITY_FIX_R1/SHOWDOWN_TB_DAL_DK_UPLOAD.csv').read_bytes()).hexdigest()
print('UPLOAD', got[:16], 'R1', want[:16], 'BYTE_IDENTICAL' if got == want else 'DIFFERENT')
