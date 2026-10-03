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


GATE_FIELDS = ('G0A', 'NFL_1')


def governance_fields(o) -> dict:
    """The governance block, read from may_publish()'s evidence and nothing else.

    OWNER RULE 1 (2026-10-02). This used to read `g.get('G0A') or '11/12'` and
    `g.get('NFL_1') or 'NOT AUTHORIZED'`: a literal where a measurement
    belongs. PROJECT_STATE.json's reading rule is that every field not ending
    `_declared` is MEASURED from the tree, and "a field nobody measured is
    null, never a plausible default". A default is neither an owner statement
    nor a measurement, and the specific defaults here were the live values, so
    a broken gate read would have written the right answer for the wrong
    reason forever. Now: a gate reading that is absent is `None` in the
    fields, plus a `governance_<GATE>_error` entry that `apply` carries into
    the written state's `measurement_errors`, naming what was not measured.

    Returns {'state', 'fields', 'errors'}; state is GOVERNANCE_MEASURED or
    GOVERNANCE_GATES_NOT_MEASURED.
    """
    g = (getattr(o, 'evidence', None) or {}).get('gates') or {}
    fields = {'may_publish': o.state.name, 'may_publish_code': o.code}
    errors = {}
    for k in GATE_FIELDS:
        v = g.get(k)
        fields[k] = v if v not in (None, '') else None
        if fields[k] is None:
            errors[f'governance_{k}_error'] = (
                f'NOT_MEASURED: may_publish() evidence carried no gates.{k} '
                f'reading (gates={sorted(g) or "absent"}); recorded as null, '
                f'no default substituted')
    return {'state': ('GOVERNANCE_GATES_NOT_MEASURED' if errors
                      else 'GOVERNANCE_MEASURED'),
            'fields': fields, 'errors': errors}


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
        # OWNER RULE 1 (2026-10-02): the gate readings used to default to
        # '11/12' / 'NOT AUTHORIZED' here; governance_fields() now records
        # null plus a measurement_errors entry when a reading is absent.
        gov = governance_fields(o)
        out['governance'] = gov['fields']
        out.update(gov['errors'])
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
    try:
        out['test_surface_measured'] = certify_test_surface(out['head_commit'])
    except Exception as e:                                   # noqa: BLE001
        out['test_surface_error'] = f'{type(e).__name__}: {e}'
    return out


def certify_test_surface(head: str) -> dict:
    """OWNER RULE 3 (2026-10-02): BUILD may not self-certify.

    The test surface is marked CURRENT only from the runner's own verdict row (suite_done) for a
    FULL run whose mode was VERIFY and whose head is this head. Anything else is recorded with the
    reason it does not certify. No row at all is NOT_EXECUTED, not CURRENT.
    """
    import json as _json
    p = REPO / 'nfl' / 'tests' / '_suite_progress.jsonl'
    rows = []
    if p.exists():
        for ln in p.read_text().splitlines():
            try:
                r = _json.loads(ln)
            except ValueError:
                continue
            if r.get('phase') == 'suite_done':
                rows.append(r)
    if not rows:
        return {'certification': 'NOT_EXECUTED', 'cause': 'EMPTY_INPUT',
                'why': 'no suite_done verdict row exists; nothing certifies the surface'}
    last = rows[-1]
    why = []
    if last.get('mode') != 'VERIFY':
        why.append(f"run mode was {last.get('mode')!r}, not VERIFY (a BUILD-mode run is self-certification)")
    if (last.get('head') or '')[:7] != (head or '')[:7]:
        why.append(f"run head {str(last.get('head'))[:7]} is not this head {str(head)[:7]}")
    if last.get('verdict') != 'PASS':
        why.append(f"run verdict was {last.get('verdict')}")
    if not last.get('n_modules') or last.get('n_checks_executed', 0) <= 0:
        why.append('run executed nothing')
    rec = {'last_verdict_row': {k: last.get(k) for k in ('run_id', 'verdict', 'n_modules',
                                                          'n_checks_executed', 'n_failing',
                                                          'mode', 'mode_boundary', 'head')}}
    if why:
        rec.update({'certification': 'NOT_CERTIFIED', 'why': why})
    else:
        rec.update({'certification': 'CURRENT', 'certified_head': head, 'certified_by_mode': 'VERIFY'})
    return rec


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
    ts = m.get('test_surface_measured')
    if ts:
        put(['test_surface', 'certification'], ts.get('certification'))
        put(['test_surface', 'certification_detail'], ts)
        put(['test_surface', 'stale'], ts.get('certification') != 'CURRENT')
        if ts.get('certification') == 'CURRENT':
            put(['test_surface', 'last_full_run_commit'], (ts.get('certified_head') or '')[:7])
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
