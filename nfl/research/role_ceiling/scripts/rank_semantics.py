"""Historical test of the depth-rank construction and the rank ceiling (research only, point-in-time).

Ranks are built from weeks STRICTLY BEFORE the scored week (role_state_history.pregame_depth) and, for 2026, the
captured depth chart lawful before kickoff (classic_slate_state.captured_qb_depth). The scored week's realised role is
the player's share of his club's targets (WR/TE) or rush attempts (RB) that week, banded with role_state's own cuts.
Only players who appeared in the scored week are graded (availability oracle, labelled), because the question is the
ordering among players who played, not who was injured."""
import collections, json, sys, pathlib
W = pathlib.Path('/home/user/p0work/nfl-w5'); sys.path.insert(0, str(W))
from nfl.tools import player_prior as PP, role_state_history as RSH, classic_slate_state as CS, role_state as RS
panel = PP.load_panel().value; pos_of = PP.position_index()
BANDS = RS.BANDS
CUTS = {'WR': ((0.22, 'ALPHA'), (0.15, 'PRIMARY'), (0.08, 'SECONDARY'), (0.03, 'ROTATIONAL')),
        'TE': ((0.22, 'ALPHA'), (0.15, 'PRIMARY'), (0.08, 'SECONDARY'), (0.03, 'ROTATIONAL')),
        'RB': ((0.55, 'ALPHA'), (0.35, 'PRIMARY'), (0.18, 'SECONDARY'), (0.06, 'ROTATIONAL'))}
def band(share, pos):
    for cut, n in CUTS[pos]:
        if share >= cut: return n
    return 'FRINGE'
def realised(season, week):
    out = {}
    for g, ss in panel['players'].items():
        pos = pos_of.get(g)
        if pos not in CUTS: continue
        r = (ss.get(str(season)) or {}).get(str(week))
        if not r or not r.get('team'): continue
        t = ((panel['teams'].get(r['team']) or {}).get(str(season)) or {}).get(str(week)) or {}
        den = t.get('targets') if pos in ('WR', 'TE') else t.get('rush_attempts')
        num = r.get('targets') if pos in ('WR', 'TE') else r.get('carries')
        if not den: continue
        out[g] = {'team': r['team'], 'pos': pos, 'share': (num or 0) / den}
    return out
KICK = {2: '2026-09-20T16:00:00Z', 3: '2026-09-27T16:00:00Z', 4: '2026-10-04T16:00:00Z'}
res = {'rank_ceiling_check': collections.defaultdict(collections.Counter), 'tie_rooms': [], 'tie_rules': collections.Counter(),
       'n_rooms_2026': 0}
seasons = {s: sorted({int(w) for g in panel['players'].values() for w in (g.get(str(s)) or {})}) for s in range(2021, 2027)}
for s, weeks in seasons.items():
    for wk in weeks:
        if wk < 4 and s < 2026: continue          # need three prior weeks of the season for a usage rank
        if s == 2026 and wk < 2: continue
        dep = RSH.pregame_depth(panel, pos_of, s, wk)
        real = realised(s, wk)
        rooms = collections.defaultdict(list)
        for g, d in dep.items():
            if d.get('pregame_rank') is None or d['position'] not in CUTS: continue
            if g not in real or real[g]['team'] != d['club']: continue   # graded only if he played for that club
            rooms[(d['club'], d['position'])].append((d['pregame_rank'], g))
        for (club, pos), mem in rooms.items():
            mem.sort()
            for i, (r, g) in enumerate(mem, 1):         # position-scoped rank among those who played
                res['rank_ceiling_check'][f'{pos}|usage_rank_{min(i, 4)}'][band(real[g]['share'], pos)] += 1
        if s == 2026:
            chart = CS.captured_qb_depth(KICK[wk])
            for (club, pos), mem in rooms.items():
                if club not in chart or pos not in chart[club]['by_pos']: continue
                order = chart[club]['by_pos'][pos]
                res['n_rooms_2026'] += 1
                rows = []
                for r, g in mem:
                    c = (order.index(g) + 1) if g in order else None
                    u = r
                    if u is None and isinstance(c, int) and c > CS.NO_USAGE_CHART_LIFT_LIMIT.get(pos, 0): c = None
                    m = min(x for x in (u, c) if isinstance(x, int))
                    rows.append({'gsis': g, 'usage': u, 'chart': c, 'min': m, 'share': round(real[g]['share'], 3)})
                top = [x for x in rows if x['min'] == min(y['min'] for y in rows)]
                if len(top) < 2: continue
                leader = max(rows, key=lambda x: x['share'])['gsis']
                by_id = sorted(top, key=lambda x: x['gsis'])[0]['gsis']           # incumbent: id order (gsis stands in for dk_id)
                by_chart = sorted(top, key=lambda x: (x['chart'] or 99, x['usage'] or 99, x['gsis']))[0]['gsis']
                by_usage = sorted(top, key=lambda x: (x['usage'] or 99, x['chart'] or 99, x['gsis']))[0]['gsis']
                res['tie_rooms'].append({'season': s, 'week': wk, 'club': club, 'pos': pos, 'tied': top, 'leader': leader,
                                         'id_pick': by_id, 'chart_pick': by_chart, 'usage_pick': by_usage})
                for k, v in (('id', by_id), ('chart', by_chart), ('usage', by_usage)):
                    res['tie_rules'][f'{k}_picks_room_leader'] += (v == leader)
                res['tie_rules']['n_tied_rooms'] += 1
                # the second tied player: what role did he realise?
                for x in top:
                    res['tie_rules'][f'tied_player_realised_{band(x["share"], pos)}'] += 1
out = {'rank_ceiling_check': {k: dict(v) for k, v in sorted(res['rank_ceiling_check'].items())},
       'tie_rules': dict(res['tie_rules']), 'n_rooms_2026_with_chart': res['n_rooms_2026'], 'tie_rooms': res['tie_rooms']}
pathlib.Path(sys.argv[1]).write_text(json.dumps(out, indent=1))
for k, v in out['rank_ceiling_check'].items():
    n = sum(v.values()); print(k, n, {b: round(v.get(b, 0) / n, 3) for b in reversed(BANDS)})
print(out['tie_rules'])
