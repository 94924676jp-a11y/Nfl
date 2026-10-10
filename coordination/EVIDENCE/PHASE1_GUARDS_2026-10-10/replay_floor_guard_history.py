#!/usr/bin/env python3.12
"""Run the floor guard over each of the last N real commits (commit vs its first parent). Read-only.

    PYTHONPATH=. python3.12 replay_floor_guard_history.py N OUT.json [REF]
"""
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from nfl.tools import floor_guard as FG  # noqa: E402


def main(n, out, ref='HEAD'):
    shas = subprocess.run(['git', '-C', str(ROOT), 'rev-list', '--first-parent', f'--max-count={n}', ref],
                          capture_output=True, text=True, check=True).stdout.split()
    rows = []
    for sha in shas:
        subj = subprocess.run(['git', '-C', str(ROOT), 'log', '-1', '--format=%s', sha], capture_output=True,
                              text=True).stdout.strip()
        try:
            rep = FG.run(ROOT, f'{sha}~1', sha)
            rows.append({'sha': sha[:10], 'subject': subj[:120], 'verdict': rep['verdict'],
                         'n_files': rep['n_files_changed'],
                         'findings': [{k: f[k] for k in ('rule', 'severity', 'path', 'detail')}
                                      for f in rep['findings'] if f['severity'] != 'info']})
        except FG.CouldNotRun as e:
            rows.append({'sha': sha[:10], 'subject': subj[:120], 'verdict': 'NOT_EXECUTED', 'why': str(e)[:200]})
    res = {'n_commits': len(rows), 'n_with_findings': sum(r['verdict'] == 'FINDINGS' for r in rows),
           'n_not_executed': sum(r['verdict'] == 'NOT_EXECUTED' for r in rows), 'commits': rows}
    pathlib.Path(out).write_text(json.dumps(res, indent=1) + '\n')
    print(f"{res['n_commits']} commits: {res['n_with_findings']} with findings, {res['n_not_executed']} not executed")


if __name__ == '__main__':
    main(int(sys.argv[1]), sys.argv[2], *(sys.argv[3:4]))
