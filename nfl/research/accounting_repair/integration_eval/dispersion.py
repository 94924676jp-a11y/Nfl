"""Dispersion benchmark from history (2021-2025 PLAYER_GAME, DK current rules): within-player-season SD of DK points
at matched mean, and within-player correlation of receptions with receiving yards / receiving TDs, against each arm."""
import json, sys, pathlib, collections
import numpy as np
REPO = pathlib.Path(__file__).resolve().parents[4]; sys.path.insert(0, str(REPO))
SCR = pathlib.Path(__import__('os').environ['EVAL_WORK'])   # scratch work dir (intermediates); required
from nfl.tools import world_accounting_check as WAC
pg = json.loads((REPO / 'nfl/warehouse/PLAYER_GAME.json').read_text())['rows']
# position: most frequent role by volume is not stored; use the slate positions only for the arms, and for history
# classify by usage: QB if pass_attempts>=10 in most games, else RB if carries > targets, else receiver.
by = collections.defaultdict(list)
for r in pg.values():
    if not (2021 <= int(r['season']) <= 2025): continue
    if not isinstance(r.get('dk_points_current_rules'), (int, float)): continue
    by[(r['player_id'], r['season'])].append(r)
hist = collections.defaultdict(list)    # group -> list of (mean, sd, corr_rec_yds, corr_rec_td)
for (pid, s), g in by.items():
    g = [r for r in g if (r['targets'] or 0) + (r['carries'] or 0) + (r['pass_attempts'] or 0) > 0]
    if len(g) < 8: continue
    pa = np.mean([r['pass_attempts'] for r in g]); car = np.mean([r['carries'] for r in g]); tg = np.mean([r['targets'] for r in g])
    grp = 'QB' if pa >= 10 else ('RB' if car > tg else 'REC')
    dk = np.array([r['dk_points_current_rules'] for r in g], float)
    rc = np.array([r['receptions'] for r in g], float); ry = np.array([r['receiving_yards'] for r in g], float)
    rt = np.array([r['receiving_td'] for r in g], float)
    c1 = float(np.corrcoef(rc, ry)[0, 1]) if rc.std() > 0 and ry.std() > 0 else None
    c2 = float(np.corrcoef(rc, rt)[0, 1]) if rc.std() > 0 and rt.std() > 0 else None
    hist[grp].append((float(dk.mean()), float(dk.std(ddof=1)), c1, c2))
BINS = [1, 4, 7, 10, 13, 16, 20, 25, 40]
def bin_of(m):
    for lo, hi in zip(BINS[:-1], BINS[1:]):
        if lo <= m < hi: return (lo, hi)
    return None
hb = {}
for grp, v in hist.items():
    for lo, hi in zip(BINS[:-1], BINS[1:]):
        sel = [x for x in v if lo <= x[0] < hi]
        if len(sel) >= 10:
            hb[(grp, lo, hi)] = {'n_player_seasons': len(sel), 'median_sd': float(np.median([x[1] for x in sel])),
                                 'median_cv': float(np.median([x[1] / x[0] for x in sel])),
                                 'median_corr_rec_yds': float(np.median([x[2] for x in sel if x[2] is not None])) if grp != 'QB' else None,
                                 'median_corr_rec_td': float(np.median([x[3] for x in sel if x[3] is not None])) if grp != 'QB' else None}
SL = {'TB_DAL_2026W5': (REPO / 'nfl/dfs/salaries/showdown_tb_dal/OFFICIAL', REPO / 'nfl/research/accounting_repair/TB_DAL_2026W5/EVENT_CONSISTENT',
                        REPO / 'nfl/research/accounting_repair/TB_DAL_2026W5/EVENT_CONSISTENT_RECEIVER_ANCHOR'),
      'ATL_NO_2026W4': (REPO / 'nfl/dfs/salaries/showdown_atl_no/RW_INACTIVES_CHARTFIX', REPO / 'nfl/research/accounting_repair/ATL_NO_2026W4/EVENT_CONSISTENT',
                        REPO / 'nfl/research/accounting_repair/ATL_NO_2026W4/EVENT_CONSISTENT_RECEIVER_ANCHOR')}
out = {'history_bins': {f'{g}:{lo}-{hi}': v for (g, lo, hi), v in hb.items()}, 'slates': {},
       'NOTE': ('within-player-season SD across games includes week-to-week role and context changes that a single-game '
                'forecast conditions away, so it is an UPPER benchmark for a well-calibrated conditional SD, not a target')}
agg = collections.defaultdict(list)
for tag, dirs in SL.items():
    arms = {}
    for name, d in zip(('inc', 'rep_qb', 'rep_rec'), dirs):
        meta, S, pts, doc, _st, _f = WAC.load(d)
        arms[name] = (meta, S, doc)
    proj = json.loads(next(dirs[0].glob('SHOWDOWN_*_PROJ.json')).read_text())
    pos = {f"{r['name']}|{r['team']}": r['position'] for r in proj['rows'].values()}
    rows = []
    for k in arms['inc'][0]['keys']:
        p = pos.get(k)
        if p not in ('QB', 'RB', 'WR', 'TE'): continue
        grp = 'QB' if p == 'QB' else ('RB' if p == 'RB' else 'REC')
        rec = {'player': k, 'pos': p}
        for a, (meta, S, doc) in arms.items():
            F = {f: i for i, f in enumerate(meta['fields'])}
            i = meta['keys'].index(k)
            dk = np.asarray(doc['draws'][k], float)
            rc, ry, rt = S[i, :, F['receptions']], S[i, :, F['rec_yards']], S[i, :, F['rec_td']]
            rec[a] = {'mean': float(dk.mean()), 'sd': float(dk.std()),
                      'corr_rec_yds': float(np.corrcoef(rc, ry)[0, 1]) if rc.std() > 0 and ry.std() > 0 else None,
                      'corr_rec_td': float(np.corrcoef(rc, rt)[0, 1]) if rc.std() > 0 and rt.std() > 0 else None}
        b = bin_of(rec['inc']['mean'])
        h = hb.get((grp, *b)) if b else None
        if h:
            rec['history_bin'] = f'{grp}:{b[0]}-{b[1]}'
            for a in ('inc', 'rep_qb', 'rep_rec'):
                rec[a]['sd_over_history_median_sd'] = rec[a]['sd'] / h['median_sd']
                agg[(grp, a)].append(rec[a]['sd'] / h['median_sd'])
                if grp != 'QB' and rec[a]['corr_rec_yds'] is not None:
                    agg[(grp, a, 'cy')].append(rec[a]['corr_rec_yds'] - h['median_corr_rec_yds'])
                if grp != 'QB' and rec[a]['corr_rec_td'] is not None:
                    agg[(grp, a, 'ct')].append(rec[a]['corr_rec_td'] - h['median_corr_rec_td'])
        rows.append(rec)
    out['slates'][tag] = rows
out['summary'] = {}
for key, v in sorted(agg.items()):
    out['summary'][':'.join(key)] = {'n_players': len(v), 'median': round(float(np.median(v)), 4), 'mean': round(float(np.mean(v)), 4),
                                     'share_above_1' if len(key) == 2 else 'share_above_0': round(float(np.mean(np.array(v) > (1 if len(key) == 2 else 0))), 3)}
pathlib.Path(sys.argv[1]).write_text(json.dumps(out, indent=1))
print(json.dumps(out['summary'], indent=0)); print(json.dumps({k: v for k, v in out['history_bins'].items()}, indent=0)[:3000])
