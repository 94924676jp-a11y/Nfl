import gzip,csv,io,re,collections,json,numpy as np
from field import parse_lineup, ours, RAWP, files
out={}
for cid in files:
    b=gzip.decompress(open(RAWP+files[cid],'rb').read()).decode('utf-8-sig')
    rows=list(csv.reader(io.StringIO(b))); h=rows[0]; L=h.index('Lineup'); N=h.index('EntryName'); E=h.index('EntryId')
    U=collections.defaultdict(list)
    for r in rows[1:]:
        if len(r)>L and r[L].strip() and r[E] not in ours:
            c,f=parse_lineup(r[L]); u=re.sub(r'\s*\(\d+/\d+\)$','',r[N].strip()); U[u].append((c,f))
    sizes=np.array([len(v) for v in U.values()])
    tot=sizes.sum()
    within=sum(len(v)-len(set(v)) for v in U.values())
    allc=collections.Counter(x for v in U.values() for x in v)
    # copies of each entry held by OTHER users
    other=[]
    for u,v in U.items():
        own=collections.Counter(v)
        for x in v: other.append(allc[x]-own[x])
    other=np.array(other)
    out[cid]={'n_users':len(U),'entries':int(tot),'share_entries_from_users_with_ge_100':round(float(sizes[sizes>=100].sum()/tot),3),
      'share_entries_from_single_entry_users':round(float(sizes[sizes==1].sum()/tot),3),'users_ge_100':int((sizes>=100).sum()),
      'within_user_duplicate_entries':int(within),'within_user_dup_share':round(within/tot,4),
      'median_copies_held_by_other_users':float(np.median(other)),'share_unique_across_users':round(float((other==0).mean()),3)}
print(json.dumps(out,indent=1)); json.dump(out,open('field_users.json','w'),indent=1)
