import pandas as pd, numpy as np, json, collections
PBP='/home/user/nfl/nfl/research/postgame/pbp_2026.2b3e9f2c6f92123f.csv.gz'   # retrieved 2026-10-07T16:59Z, weeks 1-4, BEFORE TB@DAL kickoff
cols=['game_id','week','posteam','defteam','home_team','away_team','play_type','pass_attempt','rush_attempt','receiver_player_name','rusher_player_name','passer_player_name',
      'yardline_100','two_point_attempt','qb_scramble','rush_touchdown','pass_touchdown','touchdown','td_player_name','field_goal_result','kick_distance','extra_point_result',
      'kicker_player_name','receiving_yards','rushing_yards','passing_yards','complete_pass','total_home_score','total_away_score','home_score','away_score','sack','interception','fumble_lost','qb_kneel','qb_spike','receiver_player_id','rusher_player_id','td_player_id','lateral_reception','lateral_rush','penalty','play_deleted' if False else 'desc']
d=pd.read_csv(PBP,low_memory=False,usecols=lambda c:c in cols)
d=d[(d.two_point_attempt!=1)]
out={'SOURCE':PBP.replace('/home/user/nfl/',''),'RETRIEVED':'2026-10-07T16:59:14Z (pre-kickoff of TB@DAL 2026-10-09T00:15Z)','weeks':[1,2,3,4]}
# team results
g=d.drop_duplicates('game_id')[['game_id','week','home_team','away_team','home_score','away_score']]
res={}
for t in ('DAL','TB'):
    rr=[]
    for r in g[(g.home_team==t)|(g.away_team==t)].sort_values('week').itertuples():
        opp=r.away_team if r.home_team==t else r.home_team
        pf=r.home_score if r.home_team==t else r.away_score; pa=r.away_score if r.home_team==t else r.home_score
        rr.append({'week':int(r.week),'opp':opp,'home':r.home_team==t,'pts_for':int(pf),'pts_allowed':int(pa)})
    res[t]=rr
out['results']=res
# opponents' season PPG excluding game vs t (quality of offenses faced)
ppg={}
for t in pd.unique(pd.concat([g.home_team,g.away_team])):
    s=[]
    for r in g.itertuples():
        if r.home_team==t: s.append(r.home_score)
        elif r.away_team==t: s.append(r.away_score)
    ppg[t]=float(np.mean(s))
lg=float(np.mean(list(ppg.values())))
out['league_mean_ppg_wk1_4']=round(lg,2)
out['TB_opponents_ppg']={r['opp']:round(ppg[r['opp']],2) for r in res['TB']}
out['DAL_opponents_ppg']={r['opp']:round(ppg[r['opp']],2) for r in res['DAL']}
# targets by week
tg=d[(d.pass_attempt==1)&d.receiver_player_name.notna()&(d.sack!=1)]
def tgt(team):
    t=tg[tg.posteam==team].groupby(['receiver_player_name','week']).size().unstack(fill_value=0)
    t['total']=t.sum(1); return t.sort_values('total',ascending=False)
TT={}
for t in ('DAL','TB'):
    x=tgt(t); TT[t]={k:{str(w):int(v) for w,v in row.items()} for k,row in x.head(14).iterrows()}
    print(t); print(x.head(14))
out['targets_by_week']=TT
# club pass attempts per week
pa=d[(d.pass_attempt==1)&(d.sack!=1)].groupby(['posteam','week']).size()
out['club_targets_or_attempts_ex_sacks']={t:{str(w):int(pa[t][w]) for w in pa[t].index} for t in ('DAL','TB')}
# rushing inside 10 / 5 (carries = rush_attempt==1 & play_type=='run' incl scrambles? exclude kneels)
ru=d[(d.rush_attempt==1)&(d.qb_kneel!=1)&d.rusher_player_name.notna()]
ru10=ru[ru.yardline_100<=10]; ru5=ru[ru.yardline_100<=5]
lead10=ru10.groupby(['rusher_player_name','posteam']).size().sort_values(ascending=False).head(8)
lead5=ru5.groupby(['rusher_player_name','posteam']).size().sort_values(ascending=False).head(8)
print(lead10); print(lead5)
out['league_inside10_carries_top8']=[{'player':a,'team':b,'n':int(n)} for (a,b),n in lead10.items()]
out['league_inside5_carries_top8']=[{'player':a,'team':b,'n':int(n)} for (a,b),n in lead5.items()]
for t in ('DAL','TB'):
    out.setdefault('club_inside10_carries_by_player',{})[t]={a:int(n) for a,n in ru10[ru10.posteam==t].groupby('rusher_player_name').size().sort_values(ascending=False).items()}
    out.setdefault('club_inside5_carries_by_player',{})[t]={a:int(n) for a,n in ru5[ru5.posteam==t].groupby('rusher_player_name').size().sort_values(ascending=False).items()}
# carries by week DAL/TB rbs + qb
for t in ('DAL','TB'):
    c=ru[ru.posteam==t].groupby(['rusher_player_name','week']).size().unstack(fill_value=0); c['total']=c.sum(1)
    out.setdefault('carries_by_week',{})[t]={k:{str(w):int(v) for w,v in row.items()} for k,row in c.sort_values('total',ascending=False).head(8).iterrows()}
    y=ru[ru.posteam==t].groupby(['rusher_player_name','week']).rushing_yards.sum().unstack(fill_value=0)
    out.setdefault('rush_yards_by_week',{})[t]={k:{str(w):float(v) for w,v in row.items()} for k,row in y.iterrows() if k in c.sort_values('total',ascending=False).head(8).index}
    print(c.sort_values('total',ascending=False).head(8))
# Daniels scrambles
dn=ru[ru.rusher_player_name.str.contains('Daniels',na=False)&(ru.posteam=='TB')]
out['daniels_rushing']={str(w):{'carries':int(len(x)),'scrambles':int(x.qb_scramble.sum()),'yards':float(x.rushing_yards.sum())} for w,x in dn.groupby('week')}
dp=d[(d.passer_player_name.str.contains('Daniels',na=False))&(d.posteam=='TB')&(d.pass_attempt==1)&(d.sack!=1)]
out['daniels_pass_attempts_by_week']={str(w):int(len(x)) for w,x in dp.groupby('week')}
# TDs by player (rush/rec) DAL
tdp=d[(d.touchdown==1)&d.td_player_name.notna()]
for t in ('DAL','TB'):
    x=tdp[tdp.posteam==t]
    rr=collections.defaultdict(lambda:{'rush_td':0,'rec_td':0})
    for r in x.itertuples():
        if r.rush_touchdown==1: rr[r.td_player_name]['rush_td']+=1
        elif r.pass_touchdown==1: rr[r.td_player_name]['rec_td']+=1
    out.setdefault('offensive_td_by_player',{})[t]=dict(rr)
# DK points per week for Egbuka, Aubrey etc
def dk_skill(name,team):
    rows={}
    for w in range(1,5):
        x=d[(d.posteam==team)&(d.week==w)]
        rec=x[(x.receiver_player_name==name)&(x.pass_attempt==1)]
        rus=x[(x.rusher_player_name==name)&(x.rush_attempt==1)]
        rcpt=int((rec.complete_pass==1).sum()); ryd=float(rec.receiving_yards.fillna(0).sum()); rtd=int(((rec.pass_touchdown==1)&(rec.td_player_name==name)).sum())
        uyd=float(rus.rushing_yards.fillna(0).sum()); utd=int(((rus.rush_touchdown==1)&(rus.td_player_name==name)).sum())
        fl=int(((x.fumble_lost==1)&((x.receiver_player_name==name)|(x.rusher_player_name==name))).sum())
        pts=rcpt+0.1*ryd+6*rtd+0.1*uyd+6*utd+3*(ryd>=100)+3*(uyd>=100)-1*fl
        rows[str(w)]={'rec':rcpt,'rec_yds':ryd,'rec_td':rtd,'rush_yds':uyd,'rush_td':utd,'fumbles_lost':fl,'dk':round(pts,2)}
    return rows
out['dk_by_week']={'Emeka Egbuka':dk_skill('E.Egbuka','TB'),'CeeDee Lamb':dk_skill('C.Lamb','DAL'),'George Pickens':dk_skill('G.Pickens','DAL'),'Ryan Flournoy':dk_skill('R.Flournoy','DAL'),'Javonte Williams':dk_skill('J.Williams','DAL'),'Bucky Irving':dk_skill('B.Irving','TB'),'Tyler Goodson':dk_skill('T.Goodson','DAL')}
def dk_k(name,team):
    rows={}
    for w in range(1,5):
        x=d[(d.posteam==team)&(d.week==w)&(d.kicker_player_name==name)]
        fg=x[x.play_type=='field_goal']; xp=x[x.play_type=='extra_point']
        made=fg[fg.field_goal_result=='made']
        pts=sum(3 if k<40 else (4 if k<50 else 5) for k in made.kick_distance)+int((xp.extra_point_result=='good').sum())
        rows[str(w)]={'fg_made':int(len(made)),'fg_att':int(len(fg)),'fg_made_distances':[int(k) for k in made.kick_distance],'xp_made':int((xp.extra_point_result=='good').sum()),'dk':pts}
    return rows
out['dk_by_week']['Brandon Aubrey']=dk_k('B.Aubrey','DAL')
json.dump(out,open('usage_facts.json','w'),indent=1)
for k in ('results','TB_opponents_ppg','DAL_opponents_ppg','league_mean_ppg_wk1_4','daniels_rushing','daniels_pass_attempts_by_week','offensive_td_by_player','club_inside10_carries_by_player','club_inside5_carries_by_player','carries_by_week'):
    print(k, json.dumps(out[k]))
for k,v in out['dk_by_week'].items(): print(k, {w:x['dk'] for w,x in v.items()})
print(out['dk_by_week']['Brandon Aubrey'])
