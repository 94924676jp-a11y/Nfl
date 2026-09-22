import sys, json, csv, pathlib, random
import numpy as np
sys.path.insert(0,'/home/user/nfl')
from nfl.production.universe import player_universe as PU, usage_vintage as UV, role_state as RS

CUT='2026-09-21T23:20:00Z'
POST='nfl/research/showdown_fixture/run_post/d90d80c0b4a7f95e'
REVIEW='nfl/research/player_review/2026_02_NYG_LA'
SAL='nfl/dfs/salaries/raw/DKEntries_NYG_LAR_SHOWDOWN_2026W2.csv'
INACT=set(json.load(open('nfl/research/showdown_fixture/INACTIVE_IDENTITY_RESOLUTION.json'))['resolved'])
DECLARED={'Matthew Stafford','Kyren Williams','Davante Adams','Konata Mumpfield',
 'Xavier Smith','Colby Parkinson','Harrison Mevis','Jaxson Dart','Cam Skattebo',
 'Malik Nabers','Malachi Fields','Darnell Mooney','Isaiah Likely','Dominic Zvada'}
EXCLUDE_NAMES={'Najee Harris'}

uni=PU.build(2026,2,'2026_02_NYG_LA',CUT).value
BYNAME={}
for r in uni:
    for k in ('display_name','football_name'):
        n=(r.get(k) or '').strip()
        if n: BYNAME.setdefault((n,r['team']), r)
pfr={r['gsis_id']:r.get('pfr_id') for r in uni}
snaps={}
for r in RS.load_snaps(2026,2).value:
    if r.get('pfr_player_id'): snaps[r['pfr_player_id']]=RS._f(r.get('offense_pct'))
usage=UV.usage_season(2026, CUT, before_week=2).value
USED={pid for (w,t,pid) in usage}

# GATED. This used to np.load the draw artifact directly, so the player
# review could BLOCK a slate and this selector would build lineups from it
# anyway. `gated_projection.load` refuses unless the review ran, matches this
# exact artifact, and returned PASS or PASS_WITH_WARNINGS.
from nfl.production.review import gated_projection as _GP
_g = _GP.load(POST, REVIEW)
if _g.state.name != 'PASS':
    raise SystemExit(f'{_g.code}: {_g.detail}')
a = _g.value['arrays']; m = _g.value['manifest']; L = _g.value['layers']
def rows(l): return {p:i for i,p in enumerate((L.get(l) or {}).get('row_ids') or [])}
DK=a['dk_scoring__dk_points']; dkr=rows('dk_scoring')
KP=a['kicking__dk_points']; kr=rows('kicking')

ALIAS={'LAR':'LA','NYG':'NYG'}
raw=list(csv.reader(open(SAL)))
entries=[r for r in raw if r and r[0].isdigit() and len(r)>9]
pl={}
for r in raw:
    if len(r)>=20 and r[15] in ('CPT','FLEX') and r[16].isdigit():
        nm=r[13].strip(); tm=ALIAS.get(r[18].strip(),r[18].strip())
        e=pl.setdefault((nm,tm),{'name':nm,'team':tm,'pos':r[11].strip(),
            'cpt_id':None,'flex_id':None,'cpt_sal':None,'flex_sal':None})
        if r[15]=='CPT': e['cpt_id']=r[14]; e['cpt_sal']=int(r[16])
        else: e['flex_id']=r[14]; e['flex_sal']=int(r[16])

pool=[]; excluded=[]
for (nm,tm),e in pl.items():
    u=BYNAME.get((nm,tm)); gid=u['gsis_id'] if u else None
    e['gsis_id']=gid
    e['snap']=snaps.get(pfr.get(gid) or '~') if gid else None
    e['has_participation']= e['snap'] is not None
    e['has_usage']= bool(gid and gid in USED)
    e['declared']= nm in DECLARED
    if gid in INACT: excluded.append((nm,'OFFICIALLY_INACTIVE')); continue
    if nm in EXCLUDE_NAMES: excluded.append((nm,'OWNER_EXCLUDED: cold-start depth-rank anchor, no measured participation or usage')); continue
    v = DK[dkr[gid]].astype(float) if (gid and gid in dkr) else (KP[kr[gid]].astype(float) if (gid and gid in kr) else None)
    if v is None: excluded.append((nm,'NO_DRAWS')); continue
    if e['cpt_id'] is None or e['flex_id'] is None: excluded.append((nm,'MISSING_DK_SLOT')); continue
    e['draws']=v; e['mean']=float(v.mean()); e['p90']=float(np.percentile(v,90))
    if e['mean']<1.5: excluded.append((nm,'NO_MEANINGFUL_SCORING_MASS mean=%.2f'%e['mean'])); continue
    # projection source
    if e['pos']=='K': e['src']='kicking layer (FG/XP attempts and makes)'
    elif not e['has_participation'] and not e['has_usage']: e['src']='COLD_START depth-rank anchor (role_prior)'
    elif e['has_participation'] and not e['has_usage']: e['src']='measured snaps, no measured usage; share from role/allocation'
    else: e['src']='measured snaps + measured usage'
    e['support']=('UNSUPPORTED_COLD_START' if e['src'].startswith('COLD_START')
                  else 'SUPPORTED' if (e['has_participation'] and e['has_usage']) or e['pos']=='K'
                  else 'PARTIAL_NO_MEASURED_USAGE')
    pool.append(e)

print('=== COLD-START CHECK on the remaining pool ===')
cs=[e for e in pool if e['support']=='UNSUPPORTED_COLD_START']
for e in cs: print('  !! %-22s mean=%.2f  %s' % (e['name'], e['mean'], e['src']))
if not cs: print('  none: no other player is projected from the Najee mechanism')
print()
print('excluded (%d):'%len(excluded))
for n,w in sorted(excluded): print('  %-22s %s' % (n,w))

# ---- lineup selection ONLY, frozen worlds ----
D=np.array([e['draws'] for e in pool]); n,ND=D.shape
CAP=50000; rng=random.Random(20260921)
idx=list(range(n)); by=lambda i: pool[i]
seen=set(); lineups=[]; tries=0
while len(lineups)<24000 and tries<800000:
    tries+=1
    c=rng.choice(idx); f=tuple(sorted(rng.sample([i for i in idx if i!=c],5)))
    if (c,f) in seen: continue
    seen.add((c,f))
    sal=by(c)['cpt_sal']+sum(by(i)['flex_sal'] for i in f)
    if sal>CAP: continue
    if len({by(c)['team']}|{by(i)['team'] for i in f})<2: continue
    lineups.append((c,f,sal))
tot=np.empty((len(lineups),ND),dtype=np.float32)
for s in range(0,len(lineups),2000):
    blk=lineups[s:s+2000]
    ci=np.array([b[0] for b in blk]); fi=np.array([b[1] for b in blk])
    tot[s:s+len(blk)]=1.5*D[ci]+D[fi].sum(axis=1)
T=83.80    # unchanged threshold from the committed run
score=(tot>=T).mean(axis=1); mean=tot.mean(axis=1); p90=np.percentile(tot,90,axis=1)
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
out=[]
for rank,(oi,c,f,sal) in enumerate(chosen,1):
    names=[by(c)['name']]+[by(i)['name'] for i in f]
    ann=[nm for nm in names if nm in ('Konata Mumpfield','Xavier Smith')]
    out.append({'rank':rank,'cpt':by(c)['name'],'cpt_id':by(c)['cpt_id'],
      'flex':[by(i)['name'] for i in f],'flex_ids':[by(i)['flex_id'] for i in f],
      'salary':int(sal),'teams':sorted({by(c)['team']}|{by(i)['team'] for i in f}),
      'p_top3pct':round(float(score[oi]),4),'mean':round(float(mean[oi]),2),
      'p90':round(float(p90[oi]),2),
      'annotation':'DECLARED_STARTER_ROLE_NOT_YET_MODELED' if ann else '',
      'annotated_players':ann})
json.dump({'threshold':T,'lineups':out,
  'exposure':{by(i)['name']:v for i,v in sorted(exp.items(),key=lambda x:-x[1])},
  'captains':{by(i)['name']:v for i,v in sorted(cexp.items(),key=lambda x:-x[1])},
  'audit':[{k:v for k,v in e.items() if k!='draws'} for e in pool if e['name'] in
           {x for l in out for x in [l['cpt']]+l['flex']}],
  'excluded':[{'player':n,'why':w} for n,w in sorted(excluded)]},
  open('/tmp/claude-0/final20.json','w'), indent=1)
print(); print('selected', len(out))
for l in out:
    print('%2d. CPT %-20s | %-62s $%d %s' % (l['rank'], l['cpt'], ', '.join(l['flex']), l['salary'], l['annotation']))
