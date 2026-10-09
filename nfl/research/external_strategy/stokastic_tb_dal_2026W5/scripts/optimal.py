import json, numpy as np, pandas as pd, collections
from load import *
d,keys,M=draws(); meta,S,P=worlds()
name2i={k.split('|')[0]:i for i,k in enumerate(keys)}
team={k.split('|')[0]:k.split('|')[1] for k in keys}
sal=salaries()
fs={r.Name:r.Salary for r in sal.itertuples() if r._5=='FLEX'} if False else None
sal.columns=[c.replace(' ','_').replace('+','plus') for c in sal.columns]
flexsal={r.Name:r.Salary for r in sal.itertuples() if r.Roster_Position=='FLEX'}
cptsal={r.Name:r.Salary for r in sal.itertuples() if r.Roster_Position=='CPT'}
pos={r.Name:r.Position for r in sal.itertuples()}
out={}
for tag,path in (('R1_ENTERED_POOL',R1),('OFFICIAL_SEALED_POOL',OFF)):
    c=pd.read_csv(path+'SHOWDOWN_TB_DAL_CANDIDATES.csv')
    cp=np.array([name2i[x] for x in c.captain]); fl=np.array([[name2i[y.strip()] for y in s.split('/')] for s in c.flex])
    sc=1.5*M[cp]+M[fl].sum(1)          # (n_cand, 2000)
    best=sc.argmax(0)
    bs=sc.max(0)
    cptf=collections.Counter(); flexf=collections.Counter(); anyf=collections.Counter()
    split=collections.Counter(); salb=collections.Counter(); ctop=0
    for w,b in enumerate(best):
        cn=c.captain[b]; fn=[y.strip() for y in c.flex[b].split('/')]
        cptf[cn]+=1
        for y in fn: flexf[y]+=1
        for y in [cn]+fn: anyf[y]+=1
        split[c.split[b]]+=1
        s=c.salary[b]; salb['50000' if s==50000 else ('49500-49900' if s>=49500 else ('48000-49400' if s>=48000 else '<48000'))]+=1
        # is captain the top DK scorer in world among all players?
        if M[:,w].argmax()==name2i[cn]: ctop+=1
    n=M.shape[1]
    allp=sorted(anyf,key=lambda k:-anyf[k])
    out[tag]={'n_candidates':int(len(c)),'n_worlds':n,
      'agreement_with_n_worlds_optimal_column':int((np.bincount(best,minlength=len(c))==c.n_worlds_optimal.values).all()),
      'sum_n_worlds_optimal_column':int(c.n_worlds_optimal.sum()),
      'mean_world_best_score':round(float(bs.mean()),2),
      'player_optimal_frequency':{p:{'team':team[p],'pos':pos.get(p),'CPT':round(cptf[p]/n,4),'FLEX':round(flexf[p]/n,4),'ANY':round(anyf[p]/n,4),'flex_salary':flexsal.get(p),'cpt_salary':cptsal.get(p)} for p in allp},
      'optimal_split_TB_DAL':{k:round(v/n,4) for k,v in sorted(split.items())},
      'optimal_salary_band':{k:round(v/n,4) for k,v in salb.items()},
      'share_worlds_optimal_captain_is_world_top_scorer':round(ctop/n,4)}
    # DST/K captain conditions and TB receiver captain conditions (R1 only)
    if tag=='R1_ENTERED_POOL':
        cpt=np.array([c.captain[b] for b in best])
        skill=[name2i[p] for p in name2i if pos.get(p) in ('QB','RB','WR','TE')]
        maxskill=M[skill].max(0)
        cond={}
        dal,tb=P[:,0],P[:,1]
        f=meta['fields']; sk=meta['keys']
        def stt(nm,fl): return S[sk.index(nm+'|'+team[nm]),:,f.index(fl)]
        tbpa=stt('Jalon Daniels','pass_att')
        for grp,names in (('DST',['Cowboys','Buccaneers']),('K',['Brandon Aubrey','Chase McLaughlin']),('TB_pass_catcher',['Emeka Egbuka','Chris Godwin Jr.','Cade Otton','Ted Hurst III','Tez Johnson','Payne Durham']),('DAL_WR1_Lamb',['CeeDee Lamb']),('TB_RB_Irving',['Bucky Irving'])):
            m=np.isin(cpt,names)
            if m.sum()==0: cond[grp]={'n_worlds':0}; continue
            cond[grp]={'n_worlds':int(m.sum()),'share':round(float(m.mean()),4),
               'mean_total_pts_when':round(float((dal+tb)[m].mean()),1),'mean_total_pts_else':round(float((dal+tb)[~m].mean()),1),
               'mean_max_skill_dk_when':round(float(maxskill[m].mean()),1),'mean_max_skill_dk_else':round(float(maxskill[~m].mean()),1),
               'mean_TB_pass_att_when':round(float(tbpa[m].mean()),1),'mean_TB_pass_att_else':round(float(tbpa[~m].mean()),1),
               'P_TB_win_when':round(float((tb>dal)[m].mean()),3)}
        out[tag]['captain_conditions']=cond
json.dump(out,open('optimal_freq.json','w'),indent=1)
for tag in out:
    o=out[tag]; print(tag,{k:v for k,v in o.items() if k not in('player_optimal_frequency','captain_conditions')})
    for p,v in list(o['player_optimal_frequency'].items())[:24]: print('  ',p,v)
print(json.dumps(out['R1_ENTERED_POOL']['captain_conditions'],indent=0))
