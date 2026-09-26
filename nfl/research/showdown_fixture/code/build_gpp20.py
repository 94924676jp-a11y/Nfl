import json, csv, itertools, random
import numpy as np
pool=json.load(open('/tmp/claude-0/pool.json'))
D=np.load('/tmp/claude-0/draws.npy')          # (n_players, n_draws)
# drop players who cannot contribute
keep=[i for i,e in enumerate(pool) if e['mean']>=1.5]
pool=[pool[i] for i in keep]; D=D[keep]
n,ND=D.shape
CAP=50000
rng=random.Random(20260921)

idx=list(range(n))
by=lambda i: pool[i]
print('building from %d players, %d worlds' % (n, ND))

# sample legal lineups
seen=set(); lineups=[]
tries=0
while len(lineups)<24000 and tries<600000:
    tries+=1
    c=rng.choice(idx)
    f=tuple(sorted(rng.sample([i for i in idx if i!=c],5)))
    key=(c,f)
    if key in seen: continue
    seen.add(key)
    sal=by(c)['cpt_sal']+sum(by(i)['flex_sal'] for i in f)
    if sal>CAP: continue
    if len({by(c)['team']}|{by(i)['team'] for i in f})<2: continue
    lineups.append((c,f,sal))
print('legal lineups sampled:', len(lineups))

# score on shared worlds, chunked
tot=np.empty((len(lineups),ND),dtype=np.float32)
CH=2000
for s in range(0,len(lineups),CH):
    blk=lineups[s:s+CH]
    ci=np.array([b[0] for b in blk]); fi=np.array([b[1] for b in blk])
    tot[s:s+len(blk)] = 1.5*D[ci] + D[fi].sum(axis=1)

pooled=tot.reshape(-1)
T=float(np.percentile(pooled,97.0))
print('GPP threshold T (97th pct of all sampled lineup-world totals) = %.2f' % T)
score=(tot>=T).mean(axis=1)
mean=tot.mean(axis=1); p90=np.percentile(tot,90,axis=1)

order=np.argsort(-score)
MAX_EXP=14; MAX_CPT=5
chosen=[]; exp={}; cexp={}
for oi in order:
    c,f,sal=lineups[oi]
    if cexp.get(c,0)>=MAX_CPT: continue
    if any(exp.get(i,0)>=MAX_EXP for i in (c,)+f): continue
    chosen.append((oi,c,f,sal)); cexp[c]=cexp.get(c,0)+1
    for i in (c,)+f: exp[i]=exp.get(i,0)+1
    if len(chosen)==20: break
print('selected', len(chosen))

out=[]
for rank,(oi,c,f,sal) in enumerate(chosen,1):
    out.append({'rank':rank,'cpt':by(c)['name'],'cpt_id':by(c)['cpt_id'],
      'flex':[by(i)['name'] for i in f],'flex_ids':[by(i)['flex_id'] for i in f],
      'salary':int(sal),'teams':sorted({by(c)['team']}|{by(i)['team'] for i in f}),
      'p_top3pct':round(float(score[oi]),4),'mean':round(float(mean[oi]),2),
      'p90':round(float(p90[oi]),2)})
json.dump({'threshold':T,'n_sampled':len(lineups),'lineups':out,
  'exposure':{by(i)['name']:v for i,v in sorted(exp.items(), key=lambda x:-x[1])},
  'captains':{by(i)['name']:v for i,v in sorted(cexp.items(), key=lambda x:-x[1])}},
  open('/tmp/claude-0/twenty.json','w'), indent=1)
for l in out:
    print('%2d. CPT %-20s | %s' % (l['rank'], l['cpt'], ', '.join(l['flex'])))
    print('    $%d %s  P(top3%%)=%.3f mean=%.1f p90=%.1f' % (l['salary'], l['teams'], l['p_top3pct'], l['mean'], l['p90']))
