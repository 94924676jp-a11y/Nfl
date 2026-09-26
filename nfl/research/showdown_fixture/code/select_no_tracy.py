import sys, json, csv, pathlib, random
import numpy as np
sys.path.insert(0,'/home/user/nfl')
from nfl.production.universe import player_universe as PU
POST='nfl/research/showdown_fixture/run_post/d90d80c0b4a7f95e'
REVIEW='nfl/research/player_review/2026_02_NYG_LA'
# GATED. This used to np.load the draw artifact directly, so the player
# review could BLOCK a slate and this selector would build lineups from it
# anyway. `gated_projection.load` refuses unless the review ran, matches this
# exact artifact, and returned PASS or PASS_WITH_WARNINGS.
from nfl.production.review import gated_projection as _GP
_g = _GP.load(POST, REVIEW)
if _g.state.name != 'PASS':
    raise SystemExit(f'{_g.code}: {_g.detail}')
a = _g.value['arrays']; m = _g.value['manifest']; L = _g.value['layers']
def R(l): return {p:i for i,p in enumerate((L.get(l) or {}).get('row_ids') or [])}
DK=a['dk_scoring__dk_points']; dkr=R('dk_scoring')
KP=a['kicking__dk_points']; kr=R('kicking')
uni=PU.build(2026,2,'2026_02_NYG_LA','2026-09-21T23:20:00Z').value
BYN={}
for r in uni:
    for k in ('display_name','football_name'):
        n=(r.get(k) or '').strip()
        if n: BYN.setdefault((n,r['team']),r)
INACT=set(json.load(open('nfl/research/showdown_fixture/INACTIVE_IDENTITY_RESOLUTION.json'))['resolved'])
ALIAS={'LAR':'LA','NYG':'NYG'}
raw=list(csv.reader(open('nfl/dfs/salaries/raw/DKEntries_NYG_LAR_SHOWDOWN_2026W2.csv')))
entries=[r for r in raw if r and r[0].isdigit() and len(r)>9]
pl={}
for r in raw:
    if len(r)>=20 and r[15] in ('CPT','FLEX') and r[16].isdigit():
        nm=r[13].strip(); tm=ALIAS.get(r[18].strip(),r[18].strip())
        e=pl.setdefault((nm,tm),{'name':nm,'team':tm,'pos':r[11].strip(),
          'cpt_id':None,'flex_id':None,'cpt_sal':None,'flex_sal':None})
        if r[15]=='CPT': e['cpt_id']=r[14]; e['cpt_sal']=int(r[16])
        else: e['flex_id']=r[14]; e['flex_sal']=int(r[16])
COLD={'Tutu Atwell','Max Klare','Tyrone Tracy Jr.'}
pool=[]
for (nm,tm),e in pl.items():
    u=BYN.get((nm,tm)); gid=u['gsis_id'] if u else None
    if gid is None or gid in INACT or nm in COLD: continue
    v = DK[dkr[gid]].astype(float) if gid in dkr else (KP[kr[gid]].astype(float) if gid in kr else None)
    if v is None or e['cpt_sal'] is None or e['flex_sal'] is None: continue
    if float(v.mean())<1.5: continue
    e['gsis_id']=gid; e['draws']=v; pool.append(e)
D=np.array([e['draws'] for e in pool]); n,ND=D.shape
by=lambda i: pool[i]
NAME2I={by(i)['name']:i for i in range(n)}
print('pool %d players, %d worlds' % (n,ND))
CAP=50000; rng=random.Random(20260922)
seen=set(); LN=[]; tries=0
while len(LN)<30000 and tries<1000000:
    tries+=1
    c=rng.choice(range(n)); f=tuple(sorted(rng.sample([i for i in range(n) if i!=c],5)))
    if (c,f) in seen: continue
    seen.add((c,f))
    sal=by(c)['cpt_sal']+sum(by(i)['flex_sal'] for i in f)
    if sal>CAP or len({by(c)['team']}|{by(i)['team'] for i in f})<2: continue
    LN.append((c,f,sal))
print('legal lineups sampled:', len(LN))
T=np.empty((len(LN),ND),dtype=np.float32)
for s in range(0,len(LN),2000):
    blk=LN[s:s+2000]
    ci=np.array([b[0] for b in blk]); fi=np.array([b[1] for b in blk])
    T[s:s+len(blk)]=1.5*D[ci]+D[fi].sum(axis=1)
# SCALE-INVARIANT: within-world rank -> percentile
NL=T.shape[0]
pct=np.empty_like(T)
for w in range(ND):
    pct[:,w]=np.argsort(np.argsort(T[:,w]))/(NL-1)
mean_pct=pct.mean(axis=1); med_pct=np.median(pct,axis=1); raw=T.mean(axis=1)
def topfreq(q):
    cut=np.quantile(T,1-q,axis=0)
    return (T>=cut).mean(axis=1)
t1,t3,t5 = topfreq(0.01), topfreq(0.03), topfreq(0.05)
import os
GEN=int(os.environ.get('GENCAP','14'))
CAPS={'Najee Harris':2}
NOCPT={'Najee Harris'}
TES={i for i in range(n) if by(i)['pos']=='TE'}
order=np.argsort(-mean_pct)
chosen=[]; exp={}; cexp={}
for oi in order:
    c,f,sal=LN[oi]; ids=(c,)+f
    if by(c)['name'] in NOCPT: continue
    if cexp.get(c,0)>=5: continue
    ok=True
    for i in ids:
        nm=by(i)['name']; lim=CAPS.get(nm, 10 if i in TES else GEN)
        if exp.get(i,0)>=lim: ok=False; break
    if not ok: continue
    chosen.append(oi); cexp[c]=cexp.get(c,0)+1
    for i in ids: exp[i]=exp.get(i,0)+1
    if len(chosen)==20: break
print('selected', len(chosen))
out=[]
for rank,oi in enumerate(chosen,1):
    c,f,sal=LN[oi]
    out.append({'rank':rank,'cpt':by(c)['name'],'cpt_id':by(c)['cpt_id'],
      'flex':[by(i)['name'] for i in f],'flex_ids':[by(i)['flex_id'] for i in f],
      'salary':int(sal),'mean_pct':round(float(mean_pct[oi]),4),
      'med_pct':round(float(med_pct[oi]),4),'raw':round(float(raw[oi]),2),
      'top1':round(float(t1[oi]),4),'top3':round(float(t3[oi]),4),'top5':round(float(t5[oi]),4)})
json.dump({'objective':'mean within-world lineup percentile (scale-invariant)',
 'lineups':out,'exposure':{by(i)['name']:v for i,v in sorted(exp.items(),key=lambda x:-x[1])},
 'captains':{by(i)['name']:v for i,v in sorted(cexp.items(),key=lambda x:-x[1])}},
 open(os.environ.get('OUT','/tmp/claude-0/nt.json'),'w'), indent=1)
import statistics as _st
mp=[l['mean_pct'] for l in out]
print('SUMMARY cap=%d  min=%.4f median=%.4f mean_top1=%.4f uniq_cpt=%d' % (GEN, min(mp), _st.median(mp), _st.fmean(l['top1'] for l in out), len({l['cpt'] for l in out})))
print('  bottom4:', [round(x,4) for x in sorted(mp)[:4]])
print('  max_exposure=%d  n_players_used=%d' % (max(exp.values()), len(exp)))
for l in out:
    print('%2d. CPT %-20s | %-60s $%d  pct=%.4f t1=%.3f t3=%.3f raw=%.1f' %
      (l['rank'],l['cpt'],', '.join(l['flex']),l['salary'],l['mean_pct'],l['top1'],l['top3'],l['raw']))
