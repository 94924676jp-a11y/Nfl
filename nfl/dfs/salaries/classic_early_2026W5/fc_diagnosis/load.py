import json, re, unicodedata
RUN='/home/user/p0work/nfl-w5/nfl/dfs/salaries/runs/w5_research/'
EB='/home/user/nfl/nfl/dfs/salaries/classic_early_2026W5/'
def norm(n): 
    n=unicodedata.normalize('NFKD',n); n=re.sub(r"[^a-z ]","",n.lower()); n=re.sub(r"\b(jr|sr|ii|iii|iv)\b","",n); return ' '.join(n.split())
inc=json.load(open(RUN+'incumbent/PROJ.json'))
tie=json.load(open(RUN+'tie1/PROJ.json'))
scn=json.load(open(RUN+'scenario_reported_outs/PROJ.json'))
st=json.load(open(RUN+'incumbent/STATE.json'))
rs=json.load(open(RUN+'incumbent/ROLE_STATE.json'))
rs_t=json.load(open(RUN+'tie1/ROLE_STATE.json'))
ev=json.load(open(EB+'WEEK5_EVIDENCE_BOARD.json'))['rows']
rb=json.load(open(EB+'WEEK5_FULL_PLAYER_RESEARCH_BOARD.json'))['rows']
def idx(rows): return {(norm(r['name']),r['team']):k for k,r in rows.items()}
