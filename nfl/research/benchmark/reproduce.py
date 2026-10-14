"""BENCHMARK_REPRODUCTION (mandate b0540a52 phase 0): regenerate every committed benchmark artifact from the current
code and compare with the committed bytes' content. Writes only to OUTDIR and prints a JSON report.

    python3.12 nfl/research/benchmark/reproduce.py OUTDIR
Run from an isolated overlay root. Fields that are timestamps by construction are excluded from the comparison."""
import hashlib
import json
import pathlib
import subprocess
import sys
import time

out = pathlib.Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
B = pathlib.Path('nfl/research/benchmark')
PY = [sys.executable]
steps = [
    ('rows_STRICT_OFF', PY + [str(B / 'player_rows.py'), 'STRICT', 'OFF', str(out / 'rows_STRICT_OFF.json')], None),
    ('rows_STRICT_ON', PY + [str(B / 'player_rows.py'), 'STRICT', 'ON', str(out / 'rows_STRICT_ON.json')], None),
    ('rows_LEGACY_ON', PY + [str(B / 'player_rows.py'), 'LEGACY', 'ON', str(out / 'rows_LEGACY_ON.json')], None),
    ('PLAYER_SCORECARD', PY + [str(B / 'player_scorecard.py'), str(out / 'rows_STRICT_OFF.json'), str(out / 'rows_STRICT_ON.json'),
                               str(out / 'rows_LEGACY_ON.json')], 'PLAYER_SCORECARD.json'),
    ('PROSPECTIVE_SCORECARD', PY + [str(B / 'prospective_scorecard.py')], 'PROSPECTIVE_SCORECARD.json'),
    ('FOUR_ARM', PY + [str(B / 'four_arm.py')], 'FOUR_ARM_EXPLORATORY.json'),
    ('DECOMPOSE_2024', PY + [str(B / 'decompose_dev.py')], 'DECOMPOSE_2024.json'),
    ('D1_ESTIMATE_2024', PY + [str(B / 'd1_estimate.py')], 'D1_ESTIMATE_2024.json'),
    ('D1_HOLDOUT_2025', PY + [str(B / 'd1_holdout.py')], 'D1_HOLDOUT_2025.json'),
    ('FORECAST_ERROR_ATLAS', PY + [str(B / 'error_atlas.py')], 'FORECAST_ERROR_ATLAS.json'),
    ('D2_PARAMS', PY + [str(B / 'd2_fit.py')], 'D2_PARAMS.json'),
    ('D2_DEV_2024', PY + [str(B / 'd2_eval.py'), '2024'], 'D2_DEV_2024.json'),
    # a deterministic recompute of the frozen look, not a new look: nothing is chosen from it
    ('D2_LOOK_2025', PY + [str(B / 'd2_eval.py'), '2025'], 'D2_LOOK_2025.json'),
    ('JOINT_CALIBRATION', PY + [str(B / 'joint_calibration.py')], 'JOINT_CALIBRATION_SCORECARD.json'),
    # reads the committed artifacts above; run last
    ('FAIR_BASELINE', PY + [str(B / 'fair_baseline_scorecard.py')], 'FAIR_BASELINE_SCORECARD.json'),
]
TIMESTAMPS = {'written_at_utc', 'at_utc'}


def strip(x):
    if isinstance(x, dict):
        return {k: strip(v) for k, v in x.items() if k not in TIMESTAMPS}
    if isinstance(x, list):
        return [strip(v) for v in x]
    return x


rep = {'artifact': 'BENCHMARK_REPRODUCTION', 'head': subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip(),
       'python': sys.version.split()[0], 'steps': []}
for name, cmd, committed in steps:
    t = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True)
    row = {'step': name, 'cmd': ' '.join(cmd[1:]), 'rc': r.returncode, 'seconds': round(time.time() - t, 1)}
    if r.returncode != 0:
        row['stderr_tail'] = r.stderr[-800:]
    elif committed:
        (out / committed).write_text(r.stdout)
        new, old = json.loads(r.stdout), json.loads((B / committed).read_text())
        row['committed_sha256'] = hashlib.sha256((B / committed).read_bytes()).hexdigest()
        row['regenerated_sha256'] = hashlib.sha256(r.stdout.encode()).hexdigest()
        row['content_identical'] = strip(new) == strip(old)
    rep['steps'].append(row)
rep['ALL_REPRODUCED'] = all(s['rc'] == 0 and s.get('content_identical', True) for s in rep['steps'])
print(json.dumps(rep, indent=1))
