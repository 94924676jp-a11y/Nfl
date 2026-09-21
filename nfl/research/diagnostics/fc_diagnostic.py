import sys, json, csv, pathlib, itertools, statistics as st
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
        if n: BYN.setdefault(n,r)
raw=list(csv.reader(open('nfl/dfs/salaries/raw/THIRDPARTY_FC_NYG_LAR_POSTINACTIVES_CONTEXT_ONLY.csv')))
hdr=raw[1]; fc=[dict(zip(hdr,r)) for r in raw[2:] if len(r)>5 and r[0].strip()]
def f(x):
    try: return float(x)
    except: return None
common=[]
for r in fc:
    nm=r['Player'].strip(); p=f(r['FC Proj'])
    u=BYN.get(nm); gid=u['gsis_id'] if u else None
    d=None
    if gid and gid in dkr: d=float(DK[dkr[gid]].mean())
    elif gid and gid in kr: d=float(KP[kr[gid]].mean())
    common.append({'player':nm,'team':r['Team'],'pos':r['Pos'],'salary':f(r['Salary']),
      'pdepth':r['pDepth'],'fc':p,'d90':d,
      'hist_blank': not (r['2025 Avg'].strip() or r['2026 Avg'].strip() or r['STDV'].strip())})
pool=[c for c in common if c['fc'] and c['fc']>0 and c['d90'] is not None]
print('common players with non-zero FC and a valid d90 projection: %d' % len(pool))
X=np.array([c['d90'] for c in pool]); Y=np.array([c['fc'] for c in pool])
def rank(v):
    o=np.argsort(np.argsort(-v)); return o+1
rx, ry = rank(X), rank(Y)
def spearman(x,y):
    a1=np.argsort(np.argsort(x)); b1=np.argsort(np.argsort(y))
    return float(np.corrcoef(a1,b1)[0,1])
def kendall(x,y):
    n=len(x); c=d=0
    for i,j in itertools.combinations(range(n),2):
        s=np.sign(x[i]-x[j])*np.sign(y[i]-y[j])
        if s>0: c+=1
        elif s<0: d+=1
    return (c-d)/(c+d), c, d
sp=spearman(X,Y); kt,conc,disc=kendall(X,Y)
pe=float(np.corrcoef(X,Y)[0,1])
b,aa=np.polyfit(X,Y,1)
pred=aa+b*X; ss_res=((Y-pred)**2).sum(); ss_tot=((Y-Y.mean())**2).sum(); r2=1-ss_res/ss_tot
ratio=Y/X
q1,q3=np.percentile(ratio,[25,75])
print('Spearman %.4f | Kendall %.4f (conc %d disc %d) | Pearson %.4f' % (sp,kt,conc,disc,pe))
print('fit: FC = %.4f + %.4f * d90   R2=%.4f' % (aa,b,r2))
print('FC/d90 ratio: median %.3f IQR [%.3f, %.3f]' % (np.median(ratio),q1,q3))
for c,i in zip(pool,range(len(pool))):
    c['d90_rank']=int(rx[i]); c['fc_rank']=int(ry[i]); c['rank_diff']=int(rx[i]-ry[i])
    c['ratio']=round(float(ratio[i]),3); c['resid']=round(float(Y[i]-pred[i]),3)
print()
print('%-22s %-4s %-4s %6s %7s %7s %5s %5s %5s %6s %7s' % ('PLAYER','TM','POS','SAL','d90','FC','dR','fR','diff','ratio','resid'))
for c in sorted(pool, key=lambda x:x['d90_rank']):
    print('%-22s %-4s %-4s %6d %7.2f %7.2f %5d %5d %5d %6.2f %+7.2f' % (c['player'][:22],c['team'],c['pos'],c['salary'],c['d90'],c['fc'],c['d90_rank'],c['fc_rank'],c['rank_diff'],c['ratio'],c['resid']))
print()
for k in (5,10,15):
    A={c['player'] for c in pool if c['d90_rank']<=k}; B={c['player'] for c in pool if c['fc_rank']<=k}
    print('top-%d overlap: %d/%d  %s' % (k,len(A&B),k, sorted(A^B) if A^B else ''))
print()
for pos in ('QB','RB','WR','TE'):
    s=[c for c in pool if c['pos']==pos]
    if len(s)>=3:
        xs=np.array([c['d90'] for c in s]); ys=np.array([c['fc'] for c in s])
        print('%s n=%d spearman=%.3f median ratio=%.2f' % (pos,len(s),spearman(xs,ys),float(np.median(ys/xs))))
    else: print('%s n=%d — too few for a rank correlation' % (pos,len(s)))
for tm in ('NYG','LAR'):
    s=[c for c in pool if c['team']==tm]
    xs=np.array([c['d90'] for c in s]); ys=np.array([c['fc'] for c in s])
    print('%s n=%d spearman=%.3f median ratio=%.2f' % (tm,len(s),spearman(xs,ys),float(np.median(ys/xs))))
json.dump({'pool':pool,'spearman':sp,'kendall':kt,'pearson':pe,'fit_a':float(aa),'fit_b':float(b),
  'r2':float(r2),'median_ratio':float(np.median(ratio)),'iqr':[float(q1),float(q3)],
  'concordant':conc,'discordant':disc,
  'fc_zero_blank_history':[c['player'] for c in common if c['hist_blank']],
  'fc_zero_with_history':[c['player'] for c in common if (not c['fc'] or c['fc']==0) and not c['hist_blank']]},
  open('/tmp/claude-0/fcdiag.json','w'), indent=1)
