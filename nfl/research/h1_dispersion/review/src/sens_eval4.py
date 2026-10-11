import sys; sys.path.insert(0,'/tmp/claude-0/h1review/src')
from lib import *
for name, f in (('CHECKA','sens_tdfix_2022_2023.csv.gz'),('DEV','sens_tdfix_2024_2025.csv.gz')):
    df = pd.read_csv(f'{R}/scored_{name}.csv.gz', dtype={'gsis': str})
    a = pd.read_csv(f'{R}/{f}', dtype={'gsis': str})
    m = df.merge(a, on=['season','week','gsis']).reset_index(drop=True); assert len(m)==len(df)
    print(name, 'max |proj change|', round((m.proj_aug-m.proj).abs().max(),3), 'mean change', round((m.proj_aug-m.proj).mean(),4))
    m['proj'] = m.proj_aug; t,_ = mark_top(m); pl = m[(m.appeared==1)&t]
    print('  top-q ratio', [round(x,4) for x in fast_ratio_boot(pl)[:3]], len(pl))
