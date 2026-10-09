import json, gzip, csv, io, collections, numpy as np
from field import parse_lineup, salaries, ours, flexsal, cptsal, team, pos, RAWP, files
cid='196438543'
b=gzip.decompress(open(RAWP+files[cid],'rb').read()).decode('utf-8-sig')
rows=list(csv.reader(io.StringIO(b))); hdr=rows[0]; L=hdr.index('Lineup'); E=hdr.index('EntryId')
F=[]
for r in rows[1:]:
    if len(r)>L and r[L].strip() and r[E] not in ours:
        c,f=parse_lineup(r[L])
        if c and len(f)==5: F.append((c,f))
n=len(F)
cnt=collections.Counter(F)
top=cnt.most_common(100)
sp=collections.Counter()
for (c,f),k in top:
    t=collections.Counter(team[x] for x in (c,)+f); sp[f"{t.get('TB',0)}-{t.get('DAL',0)}"]+=1
cpt_team=collections.Counter(team[c] for c,f in F)
tb_sal=[]; dal_sal=[]; tb_cheap=0; tb_slots=0
big={'CeeDee Lamb','Dak Prescott','Javonte Williams','George Pickens'}
nbig=[]
for c,f in F:
    for x in f:
        if team[x]=='TB':
            tb_slots+=1; tb_cheap+= flexsal[x]<=5000; tb_sal.append(flexsal[x])
        else: dal_sal.append(flexsal[x])
    nbig.append(len(big&set((c,)+f)))
out={'top100_duped_lineups_split_TB_DAL':dict(sp),'captain_team_share':{k:round(v/n,4) for k,v in cpt_team.items()},
 'mean_flex_salary_TB_slot':round(float(np.mean(tb_sal))),'mean_flex_salary_DAL_slot':round(float(np.mean(dal_sal))),
 'share_TB_flex_slots_salary_le_5000':round(tb_cheap/tb_slots,4),
 'dist_n_of_big4_DAL':{k:round(v/n,4) for k,v in sorted(collections.Counter(nbig).items())}}
print(out); json.dump(out,open('field_actual_extra.json','w'),indent=1)
