import json, csv, numpy as np, pandas as pd
R='/home/user/nfl/nfl/dfs/salaries/showdown_tb_dal/'
OFF=R+'OFFICIAL/'
R1=R+'OFFICIAL_ELIGIBILITY_FIX_R1/'
RAW='/home/user/nfl/nfl/dfs/salaries/raw/showdown_tb_dal_2026W5/'
def salaries():
    rows=[]
    with open(RAW+'DKEntries_TB_DAL_SHOWDOWN_2026W5.5d559e413e680cae.csv') as f:
        r=csv.reader(f)
        hdr=None
        for row in r:
            if 'Name + ID' in row:
                i=row.index('Position'); hdr=(i,row[i:]); continue
            if hdr and len(row)>hdr[0]+5 and row[hdr[0]]:
                i=hdr[0]; rows.append(dict(zip(hdr[1],row[i:])))
    df=pd.DataFrame(rows); df['Salary']=df.Salary.astype(int); df['Name']=df.Name.str.strip()
    return df
def draws():
    d=json.load(open(OFF+'SHOWDOWN_TB_DAL_2026W5_DRAWS.json'))
    keys=list(d['draws'].keys())
    M=np.array([d['draws'][k] for k in keys],dtype=float)
    return d,keys,M
def worlds():
    z=np.load(OFF+'SHOWDOWN_TB_DAL_2026W5_WORLDS.npz')
    meta=json.loads(bytes(z['meta']).decode())
    S=z['stats'].astype(float)
    for fld in meta['yard_fields']:
        j=meta['fields'].index(fld); S[:,:,j]/=meta['yard_scale']
    return meta,S,z['points'][0]
