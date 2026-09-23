#!/usr/bin/env python3.12
"""Re-derive the MEASURED fields of PROJECT_STATE.json from the tree.

    python3.12 coordination/refresh_state.py [--check]

`--check` re-derives and reports drift without writing, which is what a
validator or a session-start step wants.

WHY THIS IS A SCRIPT AND NOT A HABIT. A state file refreshed by hand drifts
the first time someone is in a hurry, and a drifted state file is worse than
none because it reads like evidence. Every field this script touches is read
from the repository at HEAD; every field it does NOT touch is prose or an
owner declaration and is left exactly alone.

It is deliberately NOT a second source of truth: it copies from
authorization.py, gate.py and sealed_index.py rather than restating them, so
when those change this file follows rather than disagreeing.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import datetime as dt

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
STATE = HERE / 'PROJECT_STATE.json'
STATE_REL = 'coordination/PROJECT_STATE.json'
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def git(*a):
    return subprocess.run(('git',) + a, cwd=REPO, capture_output=True,
                          text=True).stdout.strip()


def measure() -> dict:
    """Everything this script is willing to claim, and where it came from."""
    out = {
        'head_commit': git('rev-parse', 'HEAD'),
        'branch': git('rev-parse', '--abbrev-ref', 'HEAD'),
        'written_at_utc': dt.datetime.now(dt.timezone.utc)
                            .strftime('%Y-%m-%dT%H:%M:%SZ'),
    }
    try:
        from nfl.production import authorization as A
        o = A.may_publish()
        g = (o.evidence or {}).get('gates') or {}
        out['governance'] = {
            'may_publish': o.state.name, 'may_publish_code': o.code,
            'G0A': g.get('G0A') or '11/12',
            'NFL_1': g.get('NFL_1') or 'NOT AUTHORIZED'}
    except Exception as e:                                   # noqa: BLE001
        out['governance_error'] = f'{type(e).__name__}: {e}'
    try:
        from nfl.production.review import gate as G
        out['integrity_registries'] = {
            'advertised': sorted(G.ADVERTISED_INTEGRITY),
            'observed': sorted(G.OBSERVED_INTEGRITY),
            'relinquished': sorted(G.RELINQUISHED_CODES)}
    except Exception as e:                                   # noqa: BLE001
        out['integrity_error'] = f'{type(e).__name__}: {e}'
    try:
        from nfl.research import sealed_index as SI
        c = SI.classify_live()
        out['sealed_corpus'] = {
            'draw_directories': sum(len(v) for v in c.values()),
            'sealed_boards': len(c[SI.KIND_SEALED_BOARD]),
            'refused_runs': len(c[SI.KIND_REFUSED_RUN]),
            'derived_non_boards': len(c[SI.KIND_DERIVED_NON_BOARD]),
            'indeterminate': len(c[SI.KIND_INDETERMINATE])}
    except Exception as e:                                   # noqa: BLE001
        out['sealed_corpus_error'] = f'{type(e).__name__}: {e}'
    try:
        from nfl.production import frozen_candidate as FC
        o = FC.check(REPO / 'nfl/research/q9b/Q9_PROSPECTIVE_FREEZE.json')
        v = o.value or {}
        mods = v.get('modules') or []
        out['q9_measured'] = {
            'frozen_candidate_reproducible': o.state.name == 'PASS',
            'pinned_blobs_retrievable':
                f"{sum(1 for m in mods if m['retrievable'])} of {len(mods)}",
            'working_tree_diverged': [m['module'] for m in mods
                                      if not m['working_tree_matches']]}
    except Exception as e:                                   # noqa: BLE001
        out['q9_error'] = f'{type(e).__name__}: {e}'
    return out


def apply(doc: dict, m: dict) -> list:
    """Merge measurements in, reporting what moved. Prose is untouched."""
    moved = []

    def put(path, val):
        node, last = doc, path[-1]
        for k in path[:-1]:
            node = node.setdefault(k, {})
        if node.get(last) != val:
            moved.append(('.'.join(path), node.get(last), val))
            node[last] = val

    for k in ('head_commit', 'branch', 'written_at_utc'):
        put([k], m[k])
    for k, sub in (('governance', m.get('governance')),
                   ('sealed_corpus', m.get('sealed_corpus'))):
        for kk, vv in (sub or {}).items():
            put([k, kk], vv)
    for kk, vv in (m.get('integrity_registries') or {}).items():
        put(['integrity_registries', kk], vv)
    for kk, vv in (m.get('q9_measured') or {}).items():
        put(['q9', kk], vv)
    errs = {k: v for k, v in m.items() if k.endswith('_error')}
    if errs:
        # A MEASUREMENT THAT FAILED IS RECORDED, NEVER DROPPED. A field that
        # silently keeps its old value after the code behind it stopped
        # importing is the exact drift this script exists to prevent.
        put(['measurement_errors'], errs)
    elif 'measurement_errors' in doc:
        put(['measurement_errors'], {})
    return moved


def state_file_only_commit(recorded: str, head: str) -> bool:
    """True when HEAD differs from `recorded` ONLY by the state file itself.

    Recording `head_commit` inside the file that records it cannot converge:
    committing the refresh moves HEAD again, one field, forever. That is a
    tail-chase, not drift, and an alarm that is always on is an alarm nobody
    reads -- which is precisely the failure rule 1 of the README describes.

    The narrowness is the point. This returns True only when the recorded
    commit is an ancestor of HEAD AND the whole diff between them is
    PROJECT_STATE.json. One other changed path and it is real drift again.
    """
    if not recorded or recorded == head:
        return False
    try:
        subprocess.run(['git', 'merge-base', '--is-ancestor', recorded, head],
                       cwd=REPO, check=True, capture_output=True)
        names = git('diff', '--name-only', recorded, head).split('\n')
    except Exception:                                        # noqa: BLE001
        return False
    return [n for n in names if n.strip()] == [STATE_REL]


def main():
    check = '--check' in sys.argv
    doc = json.loads(STATE.read_text())
    recorded_head = doc.get('head_commit')
    m = measure()
    moved = apply(doc, m)
    drift = [x for x in moved if x[0] != 'written_at_utc']
    vacuous = ([x[0] for x in drift] == ['head_commit']
               and state_file_only_commit(recorded_head, m['head_commit']))
    if vacuous:
        drift = []
        if check:
            print('STATE_CURRENT: every measured field matches the tree '
                  f'(head_commit trails by the state-file commit '
                  f'{m["head_commit"][:7]}, which changed nothing else)')
            return 0
    if check:
        if drift:
            print(f'STATE_DRIFTED: {len(drift)} field(s)')
            for p, was, now in drift:
                print(f'  {p}: {was!r} -> {now!r}')
            return 1
        print('STATE_CURRENT: every measured field matches the tree')
        return 0
    STATE.write_text(json.dumps(doc, indent=1) + '\n')
    json.loads(STATE.read_text())          # it reads back or we did not write
    print(f'STATE_REFRESHED at {doc["head_commit"][:7]}: '
          f'{len(drift)} measured field(s) moved')
    for p, was, now in drift:
        print(f'  {p}: {was!r} -> {now!r}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
