import gzip, csv, io, json, re, collections, numpy as np
from load import *
RAWP='/home/user/nfl/nfl/postgame/raw/showdown_tb_dal_2026W5/'
files={'196438543':'DK_STANDINGS_196438543.fa3cbd66c92db5c8.csv.gz','196438555':'DK_STANDINGS_196438555.71d388ff4c95c5ae.csv.gz','196438556':'DK_STANDINGS_196438556.abc3cc118e4b5ce5.csv.gz'}
sal=salaries(); sal.columns=[c.replace(' ','_').replace('+','plus') for c in sal.columns]
flexsal={r.Name:r.Salary for r in sal.itertuples() if r.Roster_Position=='FLEX'}
cptsal={r.Name:r.Salary for r in sal.itertuples() if r.Roster_Position=='CPT'}
team={r.Name:r.TeamAbbrev for r in sal.itertuples()}
pos={r.Name:r.Position for r in sal.itertuples()}
names=sorted(flexsal,key=len,reverse=True)
# our entries
ours=set()
st=json.load(open('/home/user/nfl/nfl/postgame/showdown_tb_dal_2026W5/TB_DAL_2026W5_STANDINGS.json'))
for cid,c in st['contests'].items():
    for e in c['ours']['entries']: ours.add(str(e['entry_id']))
def parse_lineup(s):
    # "CPT A FLEX B FLEX C ..."
    toks=re.split(r'\s*(CPT|FLEX)\s+', ' '+s.strip())
    cpt=None; flex=[]
    i=1
    while i<len(toks)-1:
        slot,nm=toks[i],toks[i+1].strip(); i+=2
        if slot=='CPT': cpt=nm
        else: flex.append(nm)
    return cpt,tuple(sorted(flex))
TARGET=frozenset(['Dak Prescott','Brandon Aubrey','CeeDee Lamb','Cowboys','Jalon Daniels','Ryan Flournoy'])
out={}
for cid,fn in files.items():
    b=gzip.decompress(open(RAWP+fn,'rb').read()).decode('utf-8-sig')
    rows=list(csv.reader(io.StringIO(b)))
    hdr=rows[0]; L=hdr.index('Lineup'); E=hdr.index('EntryId'); Pt=hdr.index('Points')
    entries=[]
    for r in rows[1:]:
        if len(r)<=L or not r[L].strip(): continue
        cpt,flex=parse_lineup(r[L])
        if cpt is None or len(flex)!=5: continue
        entries.append((r[E],cpt,flex,float(r[Pt])))
    field=[e for e in entries if e[0] not in ours]
    cnt=collections.Counter((e[1],e[2]) for e in field)
    unk=set()
    def salary(c,f):
        try: return cptsal[c]+sum(flexsal[x] for x in f)
        except KeyError as k: unk.add(str(k)); return None
    sals=np.array([s for s in (salary(e[1],e[2]) for e in field) if s is not None])
    # salary distribution
    hist={'50000':float((sals==50000).mean()),'49500-49900':float(((sals>=49500)&(sals<50000)).mean()),'49000-49400':float(((sals>=49000)&(sals<49500)).mean()),
          '48000-48900':float(((sals>=48000)&(sals<49000)).mean()),'<48000':float((sals<48000).mean())}
    q=np.percentile(sals,[1,5,10,25,50,75,90])
    # per-lineup copies vs salary
    lu=list(cnt.items())
    lsal=np.array([salary(c,f) for (c,f),n in lu]); lcnt=np.array([n for _,n in lu])
    entries_w=lcnt
    def wshare(mask): return float(entries_w[mask].sum()/entries_w.sum())
    # dup by salary band: mean copies per entry
    def dup_by(mask):
        # for entries in band, mean count of other copies
        m=mask; return float(((lcnt[m]-1)*lcnt[m]).sum()/max(1,lcnt[m].sum()))
    bands={'50000':lsal==50000,'49500-49900':(lsal>=49500)&(lsal<50000),'49000-49400':(lsal>=49000)&(lsal<49500),'48000-48900':(lsal>=48000)&(lsal<49000),'<48000':lsal<48000}
    dupband={k:{'entry_share':round(wshare(m),4),'mean_other_copies_per_entry':round(dup_by(m),1),'n_distinct':int(m.sum())} for k,m in bands.items()}
    top=cnt.most_common(25)
    toprows=[]
    for (c,f),n in top:
        s=salary(c,f); tms=collections.Counter(team[x] for x in (c,)+f)
        toprows.append({'copies':n,'cpt':c,'flex':list(f),'salary':s,'split_TB_DAL':f"{tms.get('TB',0)}-{tms.get('DAL',0)}",'points':next(e[3] for e in field if e[1]==c and e[2]==f)})
    # target lineup search
    tgt=collections.Counter()
    for (c,f),n in cnt.items():
        if frozenset((c,)+f)==TARGET: tgt[c]+=n
    tgt_rank={}
    ranked=[k for k,_ in cnt.most_common()]
    for (c,f),n in cnt.items():
        if frozenset((c,)+f)==TARGET: tgt_rank[c]=ranked.index((c,f))+1
    # team split of field
    split=collections.Counter()
    for e in field:
        tms=collections.Counter(team[x] for x in (e[1],)+e[2]); split[f"{tms.get('TB',0)}-{tms.get('DAL',0)}"]+=1
    # concentration: share of entries in top-k lineups
    srt=np.sort(lcnt)[::-1]
    conc={f'top{k}':round(float(srt[:k].sum()/srt.sum()),4) for k in (1,10,100,1000)}
    # copies distribution: share of entries whose lineup has n copies total
    tot=lcnt
    dist={'1':float(tot[tot==1].sum()/tot.sum()),'2-5':float(tot[(tot>=2)&(tot<=5)].sum()/tot.sum()),'6-20':float(tot[(tot>=6)&(tot<=20)].sum()/tot.sum()),'21-100':float(tot[(tot>=21)&(tot<=100)].sum()/tot.sum()),'101+':float(tot[tot>100].sum()/tot.sum())}
    out[cid]={'n_field_entries_parsed':len(field),'n_our_entries_parsed':len(entries)-len(field),'n_distinct_field_lineups':len(cnt),
      'salary_quantiles_p1_p5_p10_p25_p50_p75_p90':[int(x) for x in q],'salary_share_by_band':{k:round(v,4) for k,v in hist.items()},'mean_salary':round(float(sals.mean())),
      'duplication_by_salary_band':dupband,'entry_share_by_lineup_copy_count':{k:round(v,4) for k,v in dist.items()},'concentration_share_of_entries_in_top_k_lineups':conc,
      'team_split_TB_DAL_share':{k:round(v/len(field),4) for k,v in sorted(split.items())},
      'most_duplicated_lineups_top25':toprows,
      'B_48_25_named_lineup':{'set':sorted(TARGET),'salary_if_flex_all':None,'copies_by_captain':dict(tgt),'total_copies_any_captain':int(sum(tgt.values())),'rank_among_field_lineups_by_captain':tgt_rank,
          'salary_by_captain':{c:salary(c,tuple(sorted(TARGET-{c}))) for c in TARGET}},
      'unknown_names':sorted(unk)}
json.dump(out,open('field_actual.json','w'),indent=1)
for cid,o in out.items():
    print(cid,{k:v for k,v in o.items() if k not in('most_duplicated_lineups_top25',)})
    for r in o['most_duplicated_lineups_top25'][:12]: print('   ',r)
