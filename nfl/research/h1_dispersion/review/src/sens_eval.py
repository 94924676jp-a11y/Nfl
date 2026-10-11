import sys; sys.path.insert(0,'/tmp/claude-0/h1review/src')
from lib import *
for name, f in (('CHECKA','sens_aug_2022_2023.csv.gz'),('DEV','sens_aug_2024_2025.csv.gz')):
    df = pd.read_csv(f'{R}/scored_{name}.csv.gz', dtype={'gsis': str})
    a = pd.read_csv(f'{R}/{f}', dtype={'gsis': str})
    m = df.merge(a, on=['season','week','gsis'], how='left')
    print(name, 'orig rows', len(df), 'matched', int(m.proj_aug.notna().sum()), 'aug pool rows', len(a), 'aug rows not in roster', int((a.in_roster==0).sum()))
    m = m[m.proj_aug.notna()].reset_index(drop=True)
    print('  mean proj orig %.3f aug %.3f' % (m.proj.mean(), m.proj_aug.mean()))
    # same scored set; membership recomputed on augmented projections within the original scored pool
    m2 = m.copy(); m2['proj'] = m2['proj_aug']
    t, thr = mark_top(m2)
    pl = m2[(m2.appeared==1)&t]
    print('  top-q ratio, augmented positions:', [round(x,4) for x in fast_ratio_boot(pl)[:3]], 'n', len(pl))
    for s in sorted(m2.season.unique()):
        print('   season', s, [round(x,4) for x in fast_ratio_boot(pl[pl.season==s])[:3]])
    pl0 = m[(m.appeared==1)&m.top]
    print('  top-q ratio, original (same rows):', [round(x,4) for x in fast_ratio_boot(pl0)[:3]])
    print('  all played, level ratio orig %.4f aug %.4f' % (m[m.appeared==1].proj.sum()/m[m.appeared==1].actual_dk.sum(), m[m.appeared==1].proj_aug.sum()/m[m.appeared==1].actual_dk.sum()))
