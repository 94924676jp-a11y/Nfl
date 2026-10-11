"""Task 3: refutation attempts on check A and development rows."""
import json, sys
import numpy as np, pandas as pd
sys.path.insert(0, '/tmp/claude-0/h1review/src')
from lib import *

pt = pd.read_csv(f'{R}/panel_teams.csv.gz', dtype={'gsis': str})
cw = pd.read_csv(f'{R}/club_weeks.csv.gz')
# club changers: >1 distinct team within a season (whole season, so this stratum is defined with hindsight)
nteams = pt.groupby(['season', 'gsis']).team.nunique()
changers = set(nteams[nteams > 1].index)
app_set = set(zip(pt.season, pt.week, pt.gsis))
team_of = {(s, w, g): t for s, w, g, t in zip(pt.season, pt.week, pt.gsis, pt.team)}
club_games = cw.groupby(['team', 'season']).week.apply(lambda x: sorted(set(x))).to_dict()
p_by_sg = pt.groupby(['season', 'gsis']).week.apply(lambda x: sorted(set(x))).to_dict()


def prior3(season, week, g):
    """(club-game version, literal-week version) of 'appeared in each of his previous 3 weeks'.
    Club = his last club before `week` (pregame info, as the harness pool uses)."""
    wks = [w for w in p_by_sg.get((season, g), []) if w < week]
    if not wks:
        return False, False
    club = team_of[(season, wks[-1], g)]
    games = [w for w in club_games.get((club, season), []) if w < week][-3:]
    a = len(games) == 3 and all((season, w, g) in app_set for w in games)
    b = all((season, week - k, g) in app_set for k in (1, 2, 3))
    return a, b


def ratio_row(sub, label, num='proj', den='actual_dk'):
    if len(sub) == 0:
        return {'label': label, 'n': 0}
    r = fast_ratio_boot(sub, num, den)
    wk = sub.groupby('widx')[[num, den]].sum()
    return {'label': label, 'ratio': round(r[0], 4), 'lo': round(r[1], 4), 'hi': round(r[2], 4), 'n': r[4], 'weeks': r[5],
            'weeks_over_1': int((wk[num] > wk[den]).sum()),
            'mean_proj': round(sub[num].mean(), 3), 'mean_act': round(sub[den].mean(), 3),
            'excess_pts': round(sub[num].mean() - sub[den].mean(), 3)}


out = {}
for name in ('CHECKA', 'DEV'):
    df = pd.read_csv(f'{R}/scored_{name}.csv.gz', dtype={'gsis': str})
    df['changer'] = [(s, g) in changers for s, g in zip(df.season, df.gsis)]
    p3 = [prior3(s, w, g) for s, w, g in zip(df.season, df.week, df.gsis)]
    df['nc3'] = [a for a, b in p3]; df['nc3_lit'] = [b for a, b in p3]
    res = []
    pl = df[df.appeared == 1]
    tq = pl[pl.top]
    res.append(ratio_row(tq, 'ALL top-quartile, played (primary)'))
    for s in sorted(df.season.unique()):
        res.append(ratio_row(tq[tq.season == s], f'season {s}'))
    for p in POS:
        res.append(ratio_row(tq[tq.pos == p], f'position {p}'))
    for s in sorted(df.season.unique()):
        for p in POS:
            res.append(ratio_row(tq[(tq.season == s) & (tq.pos == p)], f'season {s} x {p}'))
    res.append(ratio_row(tq[~tq.changer], 'excluding in-season club changers'))
    res.append(ratio_row(tq[tq.changer], 'club changers only'))
    # top 9 % per position-week (pool threshold), and pooled top 9 % of played
    t9, _ = mark_top(df, q=0.91)
    res.append(ratio_row(df[(df.appeared == 1) & t9], 'top 9% per position-week (pool threshold), played'))
    s_ = pl.sort_values('proj', kind='stable'); n = len(s_)
    res.append(ratio_row(s_.iloc[int(np.ceil(0.91 * n)):], 'top 9% pooled over played rows'))
    # within the top quartile but below the top 9 %
    res.append(ratio_row(df[(df.appeared == 1) & df.top & ~t9], 'top quartile excluding top 9% (q75..q91)'))
    # tie / convention variants
    tstrict, _ = mark_top(df, mode='strict')
    res.append(ratio_row(df[(df.appeared == 1) & tstrict], 'strict p > q75'))
    rr = []
    for seed in range(50):
        tr, _ = mark_top(df, mode='rank', rng=np.random.default_rng(seed))
        rr.append(fast_ratio_boot(df[(df.appeared == 1) & tr], B=10)[0])
    tr, _ = mark_top(df, mode='rank', rng=np.random.default_rng(0))
    row = ratio_row(df[(df.appeared == 1) & tr], 'rank-based top 25% by count (random tie-break, seed 0)')
    row['ratio_range_over_50_tiebreak_seeds'] = [round(min(rr), 4), round(max(rr), 4)]
    row['pool_share_selected'] = round(float(tr.mean()), 4)
    res.append(row)
    # numpy 'lower' convention: v[floor(0.75 (n-1))], inclusive (includes one more order statistic)
    tl, _ = mark_top(df, qfun=lambda v: np.sort(v)[int(np.floor(0.75 * (len(v) - 1)))])
    res.append(ratio_row(df[(df.appeared == 1) & tl], "inclusive 'lower' percentile v[floor(.75(n-1))]"))
    # unconditional: all pool candidates in top quartile, non-players scored 0 (kept separate)
    tqu = df[df.top]
    row = ratio_row(tqu, 'UNCONDITIONAL top quartile, every pool candidate, absent = 0')
    row['appearance_rate'] = round(tqu.appeared.mean(), 4)
    res.append(row)
    # appearance selection
    sel = {}
    for lab, m in (('near-certain (appeared in each of his club\'s previous 3 games)', tqu.nc3),
                   ('others', ~tqu.nc3),
                   ('near-certain, literal weeks w-1..w-3', tqu.nc3_lit),
                   ('others, literal', ~tqu.nc3_lit)):
        sub = tqu[m]
        sel[lab] = {'n_pool': int(len(sub)), 'appearance_rate': round(sub.appeared.mean(), 4),
                    'conditional': ratio_row(sub[sub.appeared == 1], lab),
                    'unconditional': ratio_row(sub, lab + ' (absent=0)')}
    # mean projection of top-quartile candidates who played vs did not play
    sel['mean_proj_top_q_played'] = round(tqu[tqu.appeared == 1].proj.mean(), 3)
    sel['mean_proj_top_q_absent'] = round(tqu[tqu.appeared == 0].proj.mean(), 3)
    # near-certain AND not a club changer
    sub = tqu[tqu.nc3 & ~tqu.changer]
    sel['near_certain_non_changer_conditional'] = ratio_row(sub[sub.appeared == 1], 'near-certain & non-changer')
    out[name] = {'rows': res, 'appearance': sel}
    # save flags for later use
    df[['season', 'week', 'gsis', 'changer', 'nc3', 'nc3_lit']].to_csv(f'{R}/flags_{name}.csv.gz', index=False)

json.dump(out, open(f'{R}/refute.json', 'w'), indent=1, default=float)
for name, o in out.items():
    print('=====', name)
    for r in o['rows']:
        print(f"{r['label'][:62]:62} {r.get('ratio','-'):>7} [{r.get('lo','-')}, {r.get('hi','-')}] n={r['n']} wks>1 {r.get('weeks_over_1','-')}/{r.get('weeks','-')} excess {r.get('excess_pts','-')}"
              + (f" app={r['appearance_rate']}" if 'appearance_rate' in r else '') + (f" range={r['ratio_range_over_50_tiebreak_seeds']}" if 'ratio_range_over_50_tiebreak_seeds' in r else ''))
    for k, v in o['appearance'].items():
        if isinstance(v, dict) and 'conditional' in v:
            c, u = v['conditional'], v['unconditional']
            print(f"  {k[:60]:60} pool n={v['n_pool']} app={v['appearance_rate']} cond {c['ratio']} [{c['lo']},{c['hi']}] n={c['n']} excess {c['excess_pts']} | uncond {u['ratio']} [{u['lo']},{u['hi']}] excess {u['excess_pts']}")
        else:
            print('  ', k, v)
