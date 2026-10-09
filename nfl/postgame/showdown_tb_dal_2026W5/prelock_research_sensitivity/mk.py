import json, sys, pathlib, numpy as np
sys.path.insert(0, '/home/user/nfl')
from nfl.tools import fc_qb_scenario_compare as FCC
from nfl.tools import roster_eligibility as RE
S = pathlib.Path('/home/user/nfl/nfl/dfs/salaries/showdown_tb_dal')
RAW = pathlib.Path('/home/user/nfl/nfl/dfs/salaries/raw/showdown_tb_dal_2026W5')
base = json.loads((S/'OFFICIAL/SHOWDOWN_TB_DAL_2026W5_DRAWS.json').read_text())
flex, _, ver = FCC.load_fc(next(RAW.glob('THIRDPARTY_FC_*IDMAPPED.c6b9607f*.csv')))
pool = RE.dk_pool('/home/user/nfl/' + 'nfl/dfs/salaries/raw/showdown_tb_dal_2026W5/DKEntries_TB_DAL_SHOWDOWN_2026W5.5d559e413e680cae.csv') if False else None
block = set(json.loads((S/'OFFICIAL_ELIGIBILITY_FIX_R1/BLOCKLIST.json').read_text()))
proj = json.loads((S/'OFFICIAL/SHOWDOWN_TB_DAL_2026W5_PROJ.json').read_text())
def pos_of(k):
    n, t = k.rsplit('|', 1)
    f = flex.get((n, t)); return f['pos'] if f else '?'
rep = {}
def write(tag, D, note):
    d = dict(base); d['draws'] = {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in D.items()}
    d['SENSITIVITY'] = note
    p = pathlib.Path(f'DRAWS_{tag}.json'); p.write_text(json.dumps(d)); return p
A = {k: np.asarray(v, float) for k, v in base['draws'].items()}
# S1 FC reference: every player recentred to FC FLEX mean
fc, mid, rd = {}, {}, {}
for k, a in A.items():
    n, t = k.rsplit('|', 1); f = (flex.get((n, t)) or {}).get('proj'); m = a.mean()
    if f is None or m <= 0: fc[k] = a; rep.setdefault('fc_kept', []).append(k); continue
    fc[k] = a * (f / m) if f > 0 else a * 0
    # S2 MID: TB QB/WR/TE moved halfway to FC; everyone else ours
    if t == 'TB' and pos_of(k) in ('QB', 'WR', 'TE'):
        mid[k] = a * (((m + f) / 2) / m); rep.setdefault('mid', {})[k] = [round(m, 2), f, round((m+f)/2, 2)]
for k, a in A.items(): mid.setdefault(k, a)
# S3 REDIST: blocked players' per-world points removed and handed to same-club eligible skill players pro rata
for t in ('TB', 'DAL'):
    bk = [k for k in A if k.endswith('|'+t) and k.rsplit('|',1)[0] in block]
    ek = [k for k in A if k.endswith('|'+t) and k.rsplit('|',1)[0] not in block and pos_of(k) in ('QB','RB','WR','TE')]
    B = sum(A[k].mean() for k in bk); E = sum(A[k].mean() for k in ek)
    for k in bk: rd[k] = A[k] * 0
    for k in ek: rd[k] = A[k] * (1 + B / E)
    rep.setdefault('redist', {})[t] = {'blocked_mass': round(B, 3), 'eligible_mass': round(E, 3), 'factor': round(1 + B/E, 5), 'blocked': bk}
for k, a in A.items(): rd.setdefault(k, a)
for tag, D, note in (('FC_REF', fc, 'RESEARCH: every player recentred to FC c6b9607f FLEX mean on our worlds'),
                     ('MID_TB', mid, 'RESEARCH: TB QB/WR/TE moved halfway to FC; uncalibrated, declared before evaluation'),
                     ('REDIST', rd, 'RESEARCH: blocked players zeroed, their volume pro rata to same-club eligible skill players')):
    write(tag, D, note)
json.dump(rep, open('SCENARIO_REPORT.json', 'w'), indent=1)
print(json.dumps(rep.get('mid'), indent=0)); print(json.dumps(rep['redist'], indent=0)); print('fc_kept', rep.get('fc_kept'))
