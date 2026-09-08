"""TD2 section 7: does player-specific TD CONVERSION persist -- and does
OPPORTUNITY persist more?

The hypothesis that opportunity persists while conversion does not is TESTED,
not assumed, and the same statistics are computed for both so the comparison
means something.
"""
import collections, json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import td2_lib as T                                            # noqa: E402


def wcorr(x, y, w):
    """Opportunity-weighted Pearson correlation. Unweighted would let a
    one-carry player-season carry the same weight as a 300-carry one."""
    x, y, w = np.asarray(x, float), np.asarray(y, float), np.asarray(w, float)
    if len(x) < 10 or w.sum() <= 0:
        return None
    mx = (x * w).sum() / w.sum(); my = (y * w).sum() / w.sum()
    cov = (w * (x - mx) * (y - my)).sum()
    vx = (w * (x - mx) ** 2).sum(); vy = (w * (y - my) ** 2).sum()
    return float(cov / np.sqrt(vx * vy)) if vx > 0 and vy > 0 else None


def main():
    OUT = {'note': 'conversion AND opportunity measured identically so the '
                   'comparison is meaningful', 'estimands': {}}
    for kind in ('rec', 'rush'):
        for label, opp, td in T.ESTIMANDS[kind]:
            if label != T.PRIMARY[kind] and 'rz' not in label:
                continue
            rs = T.load(kind, opp, td)
            key = f'{kind}|{label}'
            d = {}

            # ---- split-half on prior games, odd vs even ------------------
            hist = collections.defaultdict(list)
            for r in sorted(rs, key=lambda x: x['ord']):
                if r['appeared'] and r['n_opp'] > 0:
                    hist[r['gsis_id']].append((r['n_td'], r['n_opp']))
            a_c, b_c, w_c, a_o, b_o, w_o = [], [], [], [], [], []
            for pid, g in hist.items():
                if len(g) < 8:
                    continue
                odd = g[0::2]; even = g[1::2]
                no, ne = sum(x[1] for x in odd), sum(x[1] for x in even)
                if no < 10 or ne < 10:
                    continue
                a_c.append(sum(x[0] for x in odd) / no)
                b_c.append(sum(x[0] for x in even) / ne)
                w_c.append(min(no, ne))
                a_o.append(no / len(odd)); b_o.append(ne / len(even))
                w_o.append(min(len(odd), len(even)))
            d['split_half'] = {
                'n_players': len(a_c),
                'conversion_r': wcorr(a_c, b_c, w_c),
                'opportunity_per_game_r': wcorr(a_o, b_o, w_o)}

            # ---- year to year --------------------------------------------
            per = collections.defaultdict(lambda: collections.Counter())
            games = collections.defaultdict(int)
            for r in rs:
                if r['appeared'] and r['n_opp'] > 0:
                    per[(r['gsis_id'], r['season'])]['k'] += r['n_td']
                    per[(r['gsis_id'], r['season'])]['n'] += r['n_opp']
                    games[(r['gsis_id'], r['season'])] += 1
            xa, ya, wa, xo, yo, wo = [], [], [], [], [], []
            for (pid, s), c in per.items():
                nx = per.get((pid, s + 1))
                if not nx or c['n'] < 20 or nx['n'] < 20:
                    continue
                xa.append(c['k'] / c['n']); ya.append(nx['k'] / nx['n'])
                wa.append(min(c['n'], nx['n']))
                xo.append(c['n'] / games[(pid, s)])
                yo.append(nx['n'] / games[(pid, s + 1)])
                wo.append(min(games[(pid, s)], games[(pid, s + 1)]))
            d['year_to_year'] = {
                'n_player_seasons': len(xa),
                'conversion_r': wcorr(xa, ya, wa),
                'opportunity_per_game_r': wcorr(xo, yo, wo)}

            # ---- prior-to-next-game, chronology safe ---------------------
            px, py, pw, ox, oy, ow = [], [], [], [], [], []
            for r in rs:
                if not T.eligible(r) or r['h_n'] < 20:
                    continue
                px.append(r['h_k'] / r['h_n']); py.append(r['n_td'] / r['n_opp'])
                pw.append(r['n_opp'])
                ox.append(r['h_opp_per_game']); oy.append(r['n_opp']); ow.append(1.0)
            d['prior_to_next_game'] = {
                'n': len(px), 'conversion_r': wcorr(px, py, pw),
                'opportunity_r': wcorr(ox, oy, ow)}

            # ---- subgroups -----------------------------------------------
            d['subgroups'] = {}
            for name, sel in (
                    ('established', lambda r: r['h_games'] >= 25),
                    ('low_history', lambda r: r['h_games'] < 10),
                    ('high_opportunity', lambda r: (r['h_opp_per_game'] or 0) >= 4),
                    ('low_opportunity', lambda r: (r['h_opp_per_game'] or 0) < 2)):
                sx, sy, sw = [], [], []
                ox2, oy2 = [], []
                for r in rs:
                    if not T.eligible(r) or r['h_n'] < 20 or not sel(r):
                        continue
                    sx.append(r['h_k'] / r['h_n']); sy.append(r['n_td'] / r['n_opp'])
                    sw.append(r['n_opp'])
                    ox2.append(r['h_opp_per_game']); oy2.append(r['n_opp'])
                d['subgroups'][name] = {
                    'n': len(sx), 'conversion_r': wcorr(sx, sy, sw),
                    'opportunity_r': wcorr(ox2, oy2, np.ones(len(ox2)))}
            for p in ('WR', 'TE', 'RB', 'QB'):
                sx, sy, sw = [], [], []
                for r in rs:
                    if not T.eligible(r) or r['h_n'] < 20 or r['position'] != p:
                        continue
                    sx.append(r['h_k'] / r['h_n']); sy.append(r['n_td'] / r['n_opp'])
                    sw.append(r['n_opp'])
                if len(sx) >= 100:
                    d['subgroups'][f'pos_{p}'] = {
                        'n': len(sx), 'conversion_r': wcorr(sx, sy, sw),
                        'opportunity_r': None}
            OUT['estimands'][key] = d
            print(f'\n== {key} ==')
            for blk in ('split_half', 'year_to_year', 'prior_to_next_game'):
                b = d[blk]
                cr = b.get('conversion_r')
                orr = b.get('opportunity_per_game_r', b.get('opportunity_r'))
                nn = b.get('n_players', b.get('n_player_seasons', b.get('n')))
                print(f'   {blk:<22} n={nn:<6} conversion r '
                      f'{"None" if cr is None else f"{cr:+.4f}":>8}   '
                      f'opportunity r {"None" if orr is None else f"{orr:+.4f}":>8}')
            for g, v in d['subgroups'].items():
                cr = v['conversion_r']
                print(f'     {g:<20} n={v["n"]:<6} conversion r '
                      f'{"None" if cr is None else f"{cr:+.4f}"}')
    json.dump(OUT, open(f'{HERE}/td2_persistence.json', 'w'), indent=1, default=str)
    print('\nwrote td2_persistence.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
