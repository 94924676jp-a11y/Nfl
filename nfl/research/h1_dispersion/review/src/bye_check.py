import sys; sys.path.insert(0,'/tmp/claude-0/h1review/src')
from lib import *
pt = pd.read_csv(f'{R}/panel_teams.csv.gz', dtype={'gsis': str})
cw = pd.read_csv(f'{R}/club_weeks.csv.gz')
cgs = set(zip(cw.team, cw.season, cw.week))
# pool club = last team before week
pt = pt.sort_values(['season','gsis','week'])
for name in ('CHECKA','DEV'):
    df = pd.read_csv(f'{R}/scored_{name}.csv.gz', dtype={'gsis': str})
    last = {}
    rec = pt.groupby(['season','gsis'])
    lk = {k: list(zip(g.week, g.team)) for k, g in rec}
    def club(s,w,g):
        t=None
        for wk,tm in lk.get((s,g),[]):
            if wk<w: t=tm
        return t
    df['club'] = [club(s,w,g) for s,w,g in zip(df.season,df.week,df.gsis)]
    df['club_plays'] = [(c,s,w) in cgs for c,s,w in zip(df.club,df.season,df.week)]
    df['moved'] = [ (s,w,g) in set() for s,w,g in zip(df.season,df.week,df.gsis)]
    print(name, 'pool rows', len(df), 'club has no game that week (bye or missing):', int((~df.club_plays).sum()),
          'of which appeared:', int(df[~df.club_plays].appeared.sum()))
    tq = df[df.top]
    print('  top-q pool', len(tq), 'club idle', int((~tq.club_plays).sum()), 'absent among club-playing', int(((tq.appeared==0)&tq.club_plays).sum()))
    print('  top-q appearance rate, club playing only:', round(tq[tq.club_plays].appeared.mean(),4))
    u = tq[tq.club_plays]; print('  unconditional ratio, club-playing only:', fast_ratio_boot(u)[:3])
    # do bye-week rows change q75 membership? recompute top over club-playing pool only
    d2 = df[df.club_plays].reset_index(drop=True)
    t2, thr2 = mark_top(d2)
    print('  top-q ratio (played) with q75 over club-playing pool only:', fast_ratio_boot(d2[(d2.appeared==1)&t2])[:3], int(((d2.appeared==1)&t2).sum()))
    df[['season','week','gsis','club','club_plays']].to_csv(f'{R}/club_{name}.csv.gz', index=False)
