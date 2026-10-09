"""Pregame state for a PAST Sunday 1:00 ET window, research only.
Inputs are point-in-time: panel weeks < week (patched load_panel), depth-chart and injury captures lawful at as_of,
pregame usage depth (weeks < week). AVAILABILITY IS AN ORACLE, labelled: the universe is the players who appeared that
week (panel row), so the comparison isolates how the engine ORDERS and CEILINGS players who played."""
import json, sys, pathlib, csv, gzip, hashlib, collections
W = pathlib.Path('/home/user/p0work/nfl-w5'); sys.path.insert(0, str(W))
wk, as_of, out = int(sys.argv[1]), sys.argv[2], pathlib.Path(sys.argv[3])
from nfl.tools import player_prior as PP
_orig = PP.load_panel
FULL = _orig().value
def _pit():
    o = _orig(); p = o.value
    for g, ss in p['players'].items():
        if '2026' in ss: ss['2026'] = {w: v for w, v in ss['2026'].items() if int(w) < wk}
    for c, ss in p['teams'].items():
        if '2026' in ss: ss['2026'] = {w: v for w, v in ss['2026'].items() if int(w) < wk}
    return o
PP.load_panel = _pit
from nfl.dfs.salaries import early_only as EO
from nfl.tools import classic_slate_state as CS, research_universe as RU
from sportsplatform.governance.outcome import Outcome
sched = list(csv.DictReader(gzip.open(W / 'nfl/vintage/schedules.1c6a93074563e68e.csv.gz', 'rt')))
games = [g for g in sched if g['season'] == '2026' and g['week'] == str(wk) and g['gametime'] == '13:00' and g['weekday'] == 'Sunday']
day = games[0]['gameday']; y, m, d = day.split('-')
kick = f'{m}/{d}/{y} 01:00PM ET'
sid = f'HIST2026W{wk}'
EO.SLATES[sid] = {'entries_blob': None, 'entries_sha': None, 'salary_blob': None, 'kickoff': kick}
side = {}
for g in games:
    side[g['away_team']] = (g['away_team'], g['home_team']); side[g['home_team']] = (g['away_team'], g['home_team'])
name_of = {}
for n, gs in PP.name_index().items():
    for g in gs: name_of.setdefault(g, n)
pos_of = PP.position_index()
rows = []
for g, ss in FULL['players'].items():
    r = (ss.get('2026') or {}).get(str(wk))
    pos = {'FB': 'RB'}.get(pos_of.get(g), pos_of.get(g))
    if not r or r.get('team') not in side or pos not in ('QB', 'RB', 'WR', 'TE') or g not in name_of: continue
    a, h = side[r['team']]
    rows.append({'dk_id': f'RU-{g}', 'dk_name': name_of[g], 'name_and_id': None, 'dk_pos': pos, 'roster_position': RU.FLEX[pos],
                 'flex_eligible': pos != 'QB', 'salary': None, 'dk_team': r['team'], 'team': r['team'], 'game_info': f'{a}@{h} {kick}',
                 'kickoff': kick, 'away': a, 'home': h, 'universe_kind': 'RESEARCH_UNIVERSE_ORACLE_APPEARED'})
for c, (a, h) in sorted(side.items()):
    rows.append({'dk_id': f'RU-DST-{c}', 'dk_name': f'{c} DST', 'name_and_id': None, 'dk_pos': 'DST', 'roster_position': 'DST', 'flex_eligible': False,
                 'salary': None, 'dk_team': c, 'team': c, 'game_info': f'{a}@{h} {kick}', 'kickoff': kick, 'away': a, 'home': h, 'universe_kind': 'RESEARCH_UNIVERSE_ORACLE_APPEARED'})
u = Outcome.ok(RU.CODE, value=rows, detail=f'{len(rows)} rows', sha256=hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest())
# the games are played now; the warehouse check looks for UNPLAYED games, so for a replay accept the played game
_orig_g = CS._games_in_warehouse
def _played_ok(season, pairs, gameday=None):
    art = json.loads(CS.SS.TEAM_GAME.read_text()); rr = art['rows'] if isinstance(art['rows'], list) else list(art['rows'].values())
    found, missing = {}, []
    for away, home in pairs:
        cand = sorted({x['game_id'] for x in rr if x.get('season') == season and {x.get('club'), x.get('opponent')} == {away, home} and int(x.get('week') or 0) == wk})
        if len(cand) != 1: missing.append({'away': away, 'home': home, 'candidates': cand}); continue
        found[(away, home)] = (cand[0], wk)
    return found, missing
CS._games_in_warehouse = _played_ok
st = CS.build(sid, as_of=as_of, research_universe=u)
print(st.state.value, st.code, st.detail)
if st.state.value != 'PASS':
    print(json.dumps(st.evidence, default=str)[:1500]); sys.exit(2)
v = st.value; v['REPLAY'] = {'week': wk, 'as_of': as_of, 'availability': 'ORACLE_APPEARED', 'panel': 'point-in-time weeks < week'}
out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps(v, default=str))
