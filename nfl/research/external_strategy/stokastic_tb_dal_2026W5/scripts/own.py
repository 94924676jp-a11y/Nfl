import json, csv, numpy as np, pandas as pd
from load import *
cid='196438543'
B=json.load(open(OFF+'SHOWDOWN_TB_DAL_SHADOW_BOARD_BLEND.json'))['contests'][cid]['leverage']
F=json.load(open(OFF+'SHOWDOWN_TB_DAL_SHADOW_BOARD_FC_ONLY.json'))['contests'][cid]['leverage']
SC=json.load(open('/home/user/nfl/nfl/research/ownership/predictions/SC_OWN_ROTATION_2_TB_DAL_2026W5_OFFICIAL.json'))['players']
st=json.load(open('/home/user/nfl/nfl/postgame/showdown_tb_dal_2026W5/TB_DAL_2026W5_STANDINGS.json'))['contests'][cid]['ownership']
opt=json.load(open('optimal_freq.json'))['R1_ENTERED_POOL']['player_optimal_frequency']
# FC proportional baseline from FC FLEX projections (pregame file, 23:06Z)
rows=list(csv.reader(open(RAW+'THIRDPARTY_FC_showdown_TB_DAL_2026W5_CONTEXT_ONLY.IDMAPPED.c6b9607f910c4568.csv')))
h=rows[1]; fc={}
for r in rows[2:]:
    if len(r)<len(h): continue
    d=dict(zip(h,r))
    if d['Pos']!='CPTN':
        try: fc[d['Player'].strip()]=float(d['FC Proj'])
        except: pass
tot=sum(fc.values())
exp=pd.read_csv(R1+'SHOWDOWN_TB_DAL_EXPOSURES.csv'); exp=exp[exp.contest_id==int(cid)]
cex=pd.read_csv(R1+'SHOWDOWN_TB_DAL_CPT_EXPOSURES.csv'); cex=cex[cex.contest_id==int(cid)]
ex={r.player:r.share*100 for r in exp.itertuples()}; cx={r.captain:r.share*100 for r in cex.itertuples()}
bl={x['player']:x for x in B}; fo={x['player']:x for x in F}; sc={x['name']:x for x in SC}
act={x['player']:x for x in st}
players=['CeeDee Lamb','George Pickens','Dak Prescott','Javonte Williams','Jalon Daniels','Bucky Irving','Tyler Goodson','Ryan Flournoy','Brandon Aubrey','Cowboys','Buccaneers','Emeka Egbuka','Cade Otton','Chris Godwin Jr.','Jake Ferguson','Kenny Gainwell','Ted Hurst III','Tez Johnson','Chase McLaughlin','Payne Durham','KaVontae Turpin','Sean Tucker','Brevyn Spann-Ford']
out=[]
for p in players:
    a=act.get(p,{}); o=opt.get(p,{})
    r={'player':p,
       'opt_CPT_pct':round(100*o.get('CPT',0),1),'opt_FLEX_pct':round(100*o.get('FLEX',0),1),
       'our_CPT_exposure_pct_R1':round(cx.get(p,0),1),'our_rostered_exposure_pct_R1':round(ex.get(p,0),1),
       'fc_FLEX_proj':fc.get(p),
       'fcprop_CPT_pct':round(100*fc.get(p,0)/tot,1) if p in fc else None,'fcprop_FLEX_pct':round(500*fc.get(p,0)/tot,1) if p in fc else None,
       'blend_CPT_pct':bl.get(p,{}).get('shadow_cpt'),'blend_FLEX_pct':bl.get(p,{}).get('shadow_flex'),
       'fconly_CPT_pct':fo.get(p,{}).get('shadow_cpt'),'fconly_FLEX_pct':fo.get(p,{}).get('shadow_flex'),
       'scown2_cand_CPT_pct':round(sc[p]['candidate_cpt_pct'],1) if p in sc else None,'scown2_cand_FLEX_pct':round(sc[p]['candidate_flex_pct'],1) if p in sc else None,
       'scown2_base_CPT_pct':round(sc[p]['baseline_cpt_pct'],1) if p in sc else None,'scown2_base_FLEX_pct':round(sc[p]['baseline_flex_pct'],1) if p in sc else None,
       'ACTUAL_field_CPT_pct':a.get('field_cpt_pct'),'ACTUAL_field_FLEX_pct':a.get('field_flex_pct')}
    # pregame leverage (optimal - BLEND forecast) and exposure - forecast
    if r['blend_CPT_pct'] is not None:
        r['pregame_CPT_leverage_opt_minus_blend']=round(r['opt_CPT_pct']-r['blend_CPT_pct'],1)
        r['pregame_FLEX_leverage_opt_minus_blend']=round(r['opt_FLEX_pct']-r['blend_FLEX_pct'],1)
    if r['fcprop_CPT_pct'] is not None:
        r['pregame_CPT_leverage_opt_minus_fcprop']=round(r['opt_CPT_pct']-r['fcprop_CPT_pct'],1)
        r['pregame_FLEX_leverage_opt_minus_fcprop']=round(r['opt_FLEX_pct']-r['fcprop_FLEX_pct'],1)
    if a:
        r['HINDSIGHT_CPT_exposure_minus_actual']=round(r['our_CPT_exposure_pct_R1']-(a.get('field_cpt_pct') or 0),1)
    out.append(r)
json.dump({'contest':cid,'NOTE':'opt = share of 2,000 frozen worlds in which the player is in the best lineup of the R1 candidate pool; BLEND/FC_ONLY = shadow boards written 23:22-23:23Z; SC-OWN-2 sealed 23:30Z; fcprop = no-fit share proportional to FC FLEX projection (FC file received 23:06Z; the baseline was computed postgame from that pregame file); ACTUAL = DK %Drafted (answer key only). Our exposure = R1 entered portfolio.','rows':out},open('ownership_compare.json','w'),indent=1)
pd.set_option('display.width',250); pd.set_option('display.max_columns',30)
df=pd.DataFrame(out).set_index('player')
print(df[['opt_CPT_pct','our_CPT_exposure_pct_R1','fcprop_CPT_pct','blend_CPT_pct','fconly_CPT_pct','scown2_cand_CPT_pct','scown2_base_CPT_pct','ACTUAL_field_CPT_pct']])
print(df[['opt_FLEX_pct','our_rostered_exposure_pct_R1','fcprop_FLEX_pct','blend_FLEX_pct','fconly_FLEX_pct','scown2_cand_FLEX_pct','scown2_base_FLEX_pct','ACTUAL_field_FLEX_pct']])
print(sum(x['shadow_cpt'] or 0 for x in B), sum(x['shadow_flex'] or 0 for x in B))
