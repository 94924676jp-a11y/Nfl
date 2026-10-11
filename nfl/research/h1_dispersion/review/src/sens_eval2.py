import sys; sys.path.insert(0,'/tmp/claude-0/h1review/src')
from lib import *
df = pd.read_csv(f'{R}/scored_CHECKA.csv.gz', dtype={'gsis': str})
for f in sys.argv[1:]:
    a = pd.read_csv(f'{R}/{f}', dtype={'gsis': str})
    m = df.merge(a, on=['season','week','gsis'], how='inner').reset_index(drop=True)
    m['proj'] = m['proj_aug']; t,_ = mark_top(m); pl = m[(m.appeared==1)&t]
    print(f, 'matched', len(m), 'mean proj %.3f' % m.proj.mean(), 'top-q ratio', [round(x,4) for x in fast_ratio_boot(pl)[:3]], 'n', len(pl))
