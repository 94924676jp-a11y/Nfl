"""Extract compact panel facts for the review (read-only on the repo)."""
import csv, gzip, sys
from nfl.tools import player_prior
po = player_prior.load_panel(); assert po.state.name == 'PASS'
panel = po.value
out = '/tmp/claude-0/h1review/panel_teams.csv.gz'
with gzip.open(out, 'wt', newline='') as fh:
    w = csv.writer(fh); w.writerow(['season','week','gsis','team','touches','snaps_field'])
    for g, ss in panel['players'].items():
        for s, wks in ss.items():
            if int(s) < 2021: continue
            for wk, d in wks.items():
                t = d.get('team')
                if t:
                    w.writerow([s, wk, g, t, (d.get('targets') or 0)+(d.get('carries') or 0)+(d.get('pass_attempts') or 0), ''])
with gzip.open('/tmp/claude-0/h1review/club_weeks.csv.gz', 'wt', newline='') as fh:
    w = csv.writer(fh); w.writerow(['team','season','week'])
    for c, ss in panel['teams'].items():
        for s, wks in ss.items():
            for wk in wks: w.writerow([c, s, wk])
k = next(iter(panel['players'])); s0 = next(iter(panel['players'][k])); w0 = next(iter(panel['players'][k][s0]))
print('player-week fields:', sorted(panel['players'][k][s0][w0].keys()))
