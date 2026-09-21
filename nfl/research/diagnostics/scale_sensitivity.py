import sys, json, csv, pathlib, random
import numpy as np
sys.path.insert(0,'/home/user/nfl')
from nfl.production.universe import player_universe as PU
POST='nfl/research/showdown_fixture/run_post/d90d80c0b4a7f95e'
m=json.loads((pathlib.Path(POST)/'player_draws_manifest.json').read_text())
a=np.load(pathlib.Path(POST)/'player_draws.npz'); L=m['layers']
def rows(l): return {p:i for i,p in enumerate((L.get(l) or {}).get('row_ids') or [])}
DK=a['dk_scoring__dk_points']; dkr=rows('dk_scoring')
KP=a['kicking__dk_points']; kr=rows('kicking')
uni=PU.build(2026,2,'2026_02_NYG_LA','2026-09-21T23:20:00Z').value
BYN={}
for r in uni:
    for k in ('display_name','football_name'):
        n=(r.get(k) or '').strip()
        if n: BYN.setdefault((n,r['team']),r)
INACT=set(json.load(open('nfl/research/showdown_fixture/INACTIVE_IDENTITY_RESOLUTION.json'))['resolved'])
ALIAS={'LAR':'LA','NYG':'NYG'}
raw=list(csv.reader(open('nfl/dfs/salaries/raw/DKEntries_NYG_LAR_SHOWDOWN_2026W2.csv')))
pl={}
for r in raw:
    if len(r)>=20 and r[15] in ('CPT','FLEX') and r[16].isdigit():
        nm=r[13].strip(); tm=ALIAS.get(r[18].strip(),r[18].strip())
        e=pl.setdefault((nm,tm),{'name':nm,'team':tm,'pos':r[11].strip(),'cpt_sal':None,'flex_sal':None})
        if r[15]=='CPT': e['cpt_sal']=int(r[16])
        else: e['flex_sal']=int(r[16])
pool=[]
for (nm,tm),e in pl.items():
    u=BYN.get((nm,tm)); gid=u['gsis_id'] if u else None
    if gid in INACT or gid is None: continue
    v = DK[dkr[gid]].astype(float) if gid in dkr else (KP[kr[gid]].astype(float) if gid in kr else None)
    if v is None or e['cpt_sal'] is None or e['flex_sal'] is None: continue
    if float(v.mean())<1.5: continue
    e['gsis_id']=gid; e['draws']=v; pool.append(e)
D=np.array([e['draws'] for e in pool]); n,ND=D.shape
by=lambda i: pool[i]
CAP=50000; rng=random.Random(20260921)
seen=set(); LN=[]; tries=0
while len(LN)<24000 and tries<800000:
    tries+=1
    c=rng.choice(range(n)); f=tuple(sorted(rng.sample([i for i in range(n) if i!=c],5)))
    if (c,f) in seen: continue
    seen.add((c,f))
    sal=by(c)['cpt_sal']+sum(by(i)['flex_sal'] for i in f)
    if sal>CAP or len({by(c)['team']}|{by(i)['team'] for i in f})<2: continue
    LN.append((c,f))
print('pool %d players, %d legal lineups, %d worlds' % (n,len(LN),ND))

def totals(Dm):
    T=np.empty((len(LN),ND),dtype=np.float32)
    for s in range(0,len(LN),2000):
        blk=LN[s:s+2000]
        ci=np.array([b[0] for b in blk]); fi=np.array([b[1] for b in blk])
        T[s:s+len(blk)]=1.5*Dm[ci]+Dm[fi].sum(axis=1)
    return T
T0=totals(D)
POSSCALE={'QB':1.30,'RB':1.44,'WR':1.43,'TE':1.81,'K':1.46}   # external diagnostic, analysis only
experiments={}
experiments['1_original']=T0
experiments['2_multiplicative_1.392']=totals(D*1.3923)
experiments['3_affine_a0.736_b1.392']=totals(0.7355+1.3923*D)
Dp=D.copy()
for i,e in enumerate(pool): Dp[i]=D[i]*POSSCALE.get(e['pos'],1.46)
experiments['4_position_scaled']=totals(Dp)

def sel(T, objective, thresh=83.80):
    if objective=='threshold': sc=(T>=thresh).mean(axis=1)
    elif objective=='mean': sc=T.mean(axis=1)
    elif objective=='world_pct':          # lineup percentile within each world, averaged
        r=np.argsort(np.argsort(T,axis=0),axis=0)/(T.shape[0]-1); sc=r.mean(axis=1)
    elif objective=='top3pct_in_world':   # P(lineup in top 3% of sampled lineups in same world)
        k=int(T.shape[0]*0.97)
        cut=np.partition(T,k,axis=0)[k]
        sc=(T>=cut).mean(axis=1)
    order=np.argsort(-sc); chosen=[]; exp={}; cexp={}
    for oi in order:
        c,f=LN[oi]
        if cexp.get(c,0)>=5 or any(exp.get(i,0)>=14 for i in (c,)+f): continue
        chosen.append(oi); cexp[c]=cexp.get(c,0)+1
        for i in (c,)+f: exp[i]=exp.get(i,0)+1
        if len(chosen)==20: break
    return chosen, sc, exp, cexp

base,_bs,bexp,bcexp = sel(T0,'threshold')
baseset=set(base); basecap={LN[o][0] for o in base}
print()
print('%-34s %-18s %6s %6s %8s' % ('EXPERIMENT','OBJECTIVE','top20','CPTov','rho_score'))
res={}
for nm,T in experiments.items():
    for obj in ('threshold','mean','world_pct','top3pct_in_world'):
        ch,sc,exp,cexp = sel(T,obj)
        ov=len(set(ch)&baseset)
        cap=len({LN[o][0] for o in ch} & basecap)
        rho=float(np.corrcoef(np.argsort(np.argsort(-_bs)),np.argsort(np.argsort(-sc)))[0,1])
        res[(nm,obj)]={'overlap':ov,'cpt_overlap':cap,'rho':rho,
          'exposure':{by(i)['name']:v for i,v in sorted(exp.items(),key=lambda x:-x[1])[:8]}}
        print('%-34s %-18s %4d/20 %4d/%-2d %8.4f' % (nm,obj,ov,cap,len(basecap),rho))
json.dump({str(k):v for k,v in res.items()}, open('/tmp/claude-0/sens.json','w'), indent=1)
