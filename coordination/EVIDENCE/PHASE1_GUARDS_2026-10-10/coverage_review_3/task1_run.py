import json, subprocess, sys, traceback
sys.path[:0] = ['/home/user/p0work/pylib', '/home/user/nfl-phase1']
from nfl.tools import floor_guard as FG
R = '/home/user/nfl-phase1'
shas = subprocess.check_output(['git', '-C', R, 'rev-list', '--first-parent', '--max-count=180', '0c5bf600~480'], text=True).split()
assert len(shas) == 180, len(shas)
out = []
for i, sha in enumerate(shas):
    rec = {'idx': i, 'pos': 481 + i, 'sha': sha,
           'subject': subprocess.check_output(['git', '-C', R, 'log', '-1', '--format=%s', sha], text=True).strip()}
    try:
        rep = FG.run(R, f'{sha}~1', sha)
        rec['n_files'] = rep['n_files_changed']
        rec['reported'] = [f for f in rep['findings'] if f['severity'] in ('high', 'medium')]
        rec['info'] = [f for f in rep['findings'] if f['severity'] not in ('high', 'medium')]
    except Exception as e:
        rec['error'] = f'{type(e).__name__}: {e}'
        rec['tb'] = traceback.format_exc()
    out.append(rec)
json.dump(out, open('/tmp/claude-0/review3/task1_raw.json', 'w'), indent=1)
flag = [r for r in out if r.get('reported')]
print('commits', len(out), 'flagged', len(flag), 'errors', sum('error' in r for r in out),
      'findings', sum(len(r.get('reported', [])) for r in out))
