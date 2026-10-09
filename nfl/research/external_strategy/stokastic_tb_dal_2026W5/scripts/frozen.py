import json, numpy as np, pandas as pd, collections
from load import *
OUT='/tmp/claude-0/-home-user-mlb-prop-system-v7/8de98087-4781-5a10-ae09-ef74590f8116/scratchpad/stokastic/work/frozen_numbers.json'
d,keys,M=draws(); meta,S,P=worlds()
f=meta['fields']; skeys=meta['keys']
def st(name, fld):
    k=[x for x in skeys if x.split('|')[0]==name][0]
    return S[skeys.index(k),:,f.index(fld)]
def dkd(name):
    k=[x for x in keys if x.split('|')[0]==name][0]; return M[keys.index(k)]
res={'SOURCE':'OFFICIAL/SHOWDOWN_TB_DAL_2026W5_WORLDS.npz + _DRAWS.json (frozen 2026-10-08T23:08Z, before 00:15Z kickoff); 2,000 worlds, seed 20261005',
     'HINDSIGHT':'none of these numbers uses any postgame data'}
dal,tb=P[:,0],P[:,1]; mg=dal-tb
n=len(mg)
def pr(x): return round(float(np.mean(x)),4)
def se(p): return round(float(np.sqrt(p*(1-p)/n)),4)
g={'mean_DAL_pts':round(float(dal.mean()),2),'mean_TB_pts':round(float(tb.mean()),2),'mean_total':round(float((dal+tb).mean()),2),
   'mean_margin_DAL_minus_TB':round(float(mg.mean()),2),'median_margin':round(float(np.median(mg)),2),
   'P_DAL_win':pr(mg>0),'P_TB_win':pr(mg<0),'P_tie_exact':pr(np.abs(mg)<1e-9),
   'P_DAL_by_20_plus':pr(mg>=20),'P_DAL_by_10_plus':pr(mg>=10),'P_TB_by_7_plus':pr(mg<=-7),
   'P_total_le_40':pr(dal+tb<=40),'P_DAL_le16_and_TB_ge24':pr((dal<=16)&(tb>=24)),
   'MC_SE_at_p0.25':se(0.25),
   'NOTE':'points are continuous draws (non-integer); "win" = margin>0. Club points and player TD counts are not mutually consistent in some worlds (D-05), so TD-based and points-based probabilities come from partly inconsistent accounting.'}
res['game_script']=g
players=['CeeDee Lamb','George Pickens','Javonte Williams','Tyler Goodson','Bucky Irving','Kenny Gainwell','Emeka Egbuka','Chris Godwin Jr.','Cade Otton','Jake Ferguson','Ryan Flournoy','Ted Hurst III','Tez Johnson','Dak Prescott','Jalon Daniels','Sean Tucker','Payne Durham','Brevyn Spann-Ford','KaVontae Turpin']
pp={}
for nm in players:
    try:
        td=st(nm,'rush_td')+st(nm,'rec_td')
    except IndexError: continue
    r={'mean_dk':round(float(dkd(nm).mean()),2),'P_anytime_TD':pr(td>=1),'P_2plus_TD':pr(td>=2),'mean_TD':round(float(td.mean()),3),
       'mean_targets':round(float(st(nm,'targets').mean()),2),'mean_carries':round(float(st(nm,'carries').mean()),2),
       'mean_rush_yds':round(float(st(nm,'rush_yards').mean()),1),'mean_rec_yds':round(float(st(nm,'rec_yards').mean()),1),
       'P_100plus_rec_yds':pr(st(nm,'rec_yards')>=100),'P_10plus_rush_yds':pr(st(nm,'rush_yards')>=10),
       'p10_dk':round(float(np.percentile(dkd(nm),10)),2),'p90_dk':round(float(np.percentile(dkd(nm),90)),2),'P_dk_lt5':pr(dkd(nm)<5)}
    if nm in ('Dak Prescott','Jalon Daniels'):
        r.update({'mean_pass_att':round(float(st(nm,'pass_att').mean()),2),'P_pass_att_lt15':pr(st(nm,'pass_att')<15),
                  'P_rush_yds_50plus':pr(st(nm,'rush_yards')>=50),'P_pass_td_lt2':pr(st(nm,'pass_td')<2),'mean_pass_td':round(float(st(nm,'pass_td').mean()),2),
                  'P_rush_yds_45_5_plus':pr(st(nm,'rush_yards')>=45.5),'rush_yds_p90':round(float(np.percentile(st(nm,'rush_yards'),90)),1),'max_rush_yds':float(st(nm,'rush_yards').max())})
    pp[nm]=r
res['players']=pp
jtd=(st('Javonte Williams','rush_td')+st('Javonte Williams','rec_td'))>=1
gtd=(st('Tyler Goodson','rush_td')+st('Tyler Goodson','rec_td'))>=1
res['joint']={'P_Javonte_TD_and_Goodson_TD':pr(jtd&gtd),'P_Javonte_TD':pr(jtd),'P_Goodson_TD':pr(gtd),'product_if_independent':round(float(jtd.mean()*gtd.mean()),4),
   'corr_TD_indicators':round(float(np.corrcoef(jtd,gtd)[0,1]),3),
   'corr_carries':round(float(np.corrcoef(st('Javonte Williams','carries'),st('Tyler Goodson','carries'))[0,1]),3),
   'corr_dk':round(float(np.corrcoef(dkd('Javonte Williams'),dkd('Tyler Goodson'))[0,1]),3),
   'n_worlds_both':int((jtd&gtd).sum())}
# irving receiving
res['irving_targets_dist']={'mean':round(float(st('Bucky Irving','targets').mean()),2),'P_0_targets':pr(st('Bucky Irving','targets')==0),'P_ge4':pr(st('Bucky Irving','targets')>=4)}
# conditional query example (A 24:49) -- capability demonstration
cq=(mg>=10)&(st('Tyler Goodson','rush_yards')>=10)&(st('Jalon Daniels','pass_td')<2)
res['conditional_query_A_24_49']={'P_DAL_by10_and_Goodson_10rush_and_Daniels_lt2_passTD':pr(cq),'n_worlds':int(cq.sum()),'USE':'capability demonstration only; no betting use'}
# DAL team TD: club TDs from stats vs points
def club_td(team):
    idx=[i for i,k in enumerate(skeys) if k.endswith('|'+team)]
    return (S[idx][:,:,f.index('rush_td')]+S[idx][:,:,f.index('rec_td')]).sum(0)
for team,pts in (('DAL',dal),('TB',tb)):
    t=club_td(team)
    res.setdefault('accounting',{})[team]={'mean_offensive_TD_from_stat_lines':round(float(t.mean()),2),'worlds_points_lt_6xTD':int((pts<6*t-1e-6).sum()),
        'corr_points_TDs':round(float(np.corrcoef(pts,t)[0,1]),3)}
# correlations among teammates
top=['Dak Prescott','CeeDee Lamb','George Pickens','Javonte Williams','Tyler Goodson','Jake Ferguson','Ryan Flournoy','Jalon Daniels','Bucky Irving','Emeka Egbuka','Chris Godwin Jr.','Cade Otton']
C=np.corrcoef(np.array([dkd(x) for x in top]))
res['dk_corr_matrix']={'players':top,'corr':np.round(C,3).tolist()}
# volume
cw=d['club_worlds']
for team in ('DAL','TB'):
    a=np.array(cw[team]); res.setdefault('club_volume',{})[team]={'mean_pass_att':round(float(a[:,0].mean()),2),'mean_rush_att':round(float(a[:,1].mean()),2),'pass_rate':round(float((a[:,0]/(a[:,0]+a[:,1])).mean()),3)}
json.dump(res,open(OUT,'w'),indent=1)
print(json.dumps(res,indent=1)[:6000])
