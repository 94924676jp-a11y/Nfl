#!/usr/bin/env python3.12
"""Trace one forecast attempt from raw evidence to output or refusal.

    python3.12 nfl/tools/trace_execution_path.py --run-dir <dir> [--json out]

THE DISTINCTION THIS EXISTS TO ENFORCE

    IMPLEMENTED != EXECUTED != TESTED != PROSPECTIVELY VALIDATED != PROMOTED

A module existing in the repository proves almost nothing. This reads a real
run and reports, per stage, which of those five it can actually establish:

* EXECUTED comes from the run's own stage record. A stage that did not run is
  not a stage that works.
* TESTED is computed, not asserted. For each stage the tracer searches
  `nfl/tests/` for its refusal code, and a stage whose refusal code appears in
  no test is reported UNTESTED. A refusal path nobody exercised is a branch
  that has never been shown to fire.
* PROSPECTIVELY VALIDATED and PROMOTED are read from the artifact's own
  governance and publication state, never inferred from the other three.

WHY TESTED IS SEARCHED RATHER THAN DECLARED

A declared test list goes stale the moment a test is renamed, and the stale
version always reads more reassuring than the truth. Searching the test tree
for the refusal code can be fooled -- a code mentioned in a comment counts --
so the tracer reports WHERE it found each one, and a reader can check. That is
weaker than a real coverage measurement and it is labelled as such rather than
presented as proof.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

SPEC_VERSION = 'execution-path-trace/1.0.0'
TESTS_DIR = _REPO / 'nfl' / 'tests'

NOT_ESTABLISHED = 'NOT_ESTABLISHED'


class TraceError(RuntimeError):
    """The trace cannot be built."""


def _load(run_dir: pathlib.Path):
    need = ('run_status.json', 'RUN_INPUT_CONTRACT.json')
    missing = [f for f in need if not (run_dir / f).exists()]
    if missing:
        raise TraceError(
            f'{run_dir} is missing {missing}; a trace of a run whose own '
            f'records cannot be read would be a trace of nothing')
    return (json.loads((run_dir / need[0]).read_text()),
            json.loads((run_dir / need[1]).read_text()))


def _test_index():
    """Map every token that looks like a refusal code to the files naming it."""
    index = {}
    if not TESTS_DIR.is_dir():
        return index
    token = re.compile(r'\b[A-Z][A-Z0-9_]{6,}\b')
    for path in sorted(TESTS_DIR.glob('test_*.py')):
        try:
            text = path.read_text(errors='replace')
        except OSError:
            continue
        for tok in set(token.findall(text)):
            index.setdefault(tok, []).append(path.name)
    return index


def trace(run_dir) -> dict:
    run_dir = pathlib.Path(run_dir)
    status, contract = _load(run_dir)
    tests = _test_index()

    entries = contract.get('entries') or {}
    families = {
        fam: {'capture_id': e.get('capture_id'), 'sha256': e.get('sha256'),
              'retrieved_at': e.get('retrieved_at'), 'blob': e.get('blob')}
        for fam, e in entries.items()}

    rows = []
    stages = status.get('stages') or []
    if not stages:
        raise TraceError('the run recorded no stages')

    for i, st in enumerate(stages):
        name = st.get('stage')
        state = st.get('state')
        # WHICH CODE WAS SEARCHED MATTERS AND IS REPORTED.
        # A stage that PASSED records no refusal_code, so the only token
        # available is its success code. Finding a test that names
        # TEAM_ENVIRONMENT_OK is much weaker evidence than finding one that
        # names a refusal the stage can actually emit: the first shows the
        # happy path was exercised, the second shows the branch that stops a
        # bad run has been made to fire. Conflating them would let a suite
        # that only ever runs clean inputs look fully covered.
        refusal = st.get('refusal_code')
        searched = refusal or st.get('code')
        code_kind = 'REFUSAL_CODE' if refusal else 'SUCCESS_CODE_ONLY'
        executed = state not in (None, 'DEFERRED', 'NOT_APPLICABLE')
        naming = tests.get(searched or '', [])
        rows.append({
            'order': i,
            'stage': name,
            'executed': executed,
            'state': state,
            'code': st.get('code'),
            'refusal_code': st.get('refusal_code'),
            'detail': (st.get('detail') or '')[:200],
            'elapsed_s': st.get('elapsed_s'),
            'spec_version': st.get('spec_version'),
            'spec_versions': st.get('spec_versions'),
            'input_hashes': st.get('input_hashes') or {},
            'input_families': sorted(st.get('input_hashes') or {}),
            'next_consumer': (stages[i + 1].get('stage')
                              if i + 1 < len(stages) else None),
            'code_searched': searched,
            'code_kind': code_kind,
            'tested': bool(naming),
            'tested_basis': (
                (f'{code_kind} {searched!r} appears in {naming}'
                 + ('. This stage passed, so only its success code was '
                    'available to search: the happy path is exercised, the '
                    'refusal branch is NOT thereby shown to fire.'
                    if code_kind == 'SUCCESS_CODE_ONLY' else ''))
                if naming else
                f'NO test file names {searched!r}. That is weaker than saying '
                f'the stage is broken and stronger than assuming it works.'),
            'governance': st.get('governance'),
        })

    executed_n = sum(1 for r in rows if r['executed'])
    untested = [r['stage'] for r in rows if not r['tested']]
    n_real_refusal = sum(1 for r in rows
                         if r['tested'] and r['code_kind'] == 'REFUSAL_CODE')
    success_only = [r['stage'] for r in rows
                    if r['tested'] and r['code_kind'] == 'SUCCESS_CODE_ONLY']

    return {
        'spec_version': SPEC_VERSION,
        'run_dir': str(run_dir),
        'run_id': status.get('run_id'),
        'game_id': contract.get('game_id'),
        'cutoff_utc': contract.get('cutoff_utc'),
        'code_commit': status.get('code_commit'),
        'candidate_identity': status.get('code_identity'),
        'evidence_families': families,
        'stages': rows,
        'n_stages': len(rows),
        'n_executed': executed_n,
        'n_not_executed': len(rows) - executed_n,
        'untested_stages': untested,
        'tested_on_success_code_only': success_only,
        'publication': status.get('publication'),
        'prospectively_validated': status.get('prospective_eligible',
                                              NOT_ESTABLISHED),
        'first_failure': status.get('first_failure'),
        'ladder': {
            'IMPLEMENTED': 'every stage below exists in the repository',
            'EXECUTED': f'{executed_n} of {len(rows)} ran in this attempt',
            'TESTED': (
                f'{len(rows) - len(untested)} of {len(rows)} have their code '
                f'named somewhere in nfl/tests/, of which only '
                f'{n_real_refusal} were searched on an actual REFUSAL code; '
                f'the rest passed and offered only a success code. This is a '
                f'text search, not a coverage measurement.'),
            'PROSPECTIVELY_VALIDATED': str(
                status.get('prospective_eligible', NOT_ESTABLISHED)),
            'PROMOTED': str((status.get('publication') or {}).get('state')),
        },
    }


def render(t: dict) -> str:
    w = max(len(r['stage'] or '?') for r in t['stages'])
    out = [f"execution path  {t['game_id']}  run {t['run_id']}",
           f"cutoff {t['cutoff_utc']}  commit {str(t['code_commit'])[:20]}",
           '',
           f"{'stage'.ljust(w)}  {'exec':<5} {'state':<14} {'tested':<6} code"]
    out.append(f"{'-' * w}  {'-' * 5} {'-' * 14} {'-' * 6} {'-' * 30}")
    for r in t['stages']:
        out.append(f"{(r['stage'] or '?').ljust(w)}  "
                   f"{('yes' if r['executed'] else 'NO'):<5} "
                   f"{str(r['state']):<14} "
                   f"{('yes' if r['tested'] else 'NO'):<6} "
                   f"{str(r['code'])[:30]}")
    out += ['', 'LADDER (each rung is established separately):']
    for k, v in t['ladder'].items():
        out.append(f'  {k:<26} {v}')
    if t['untested_stages']:
        out.append('')
        out.append(f"NO TEST NAMES THESE CODES AT ALL: {t['untested_stages']}")
    if t.get('tested_on_success_code_only'):
        out.append('')
        out.append('MATCHED ON A SUCCESS CODE ONLY -- the happy path is '
                   'exercised, the refusal branch is not thereby shown to '
                   'fire:')
        out.append(f"  {t['tested_on_success_code_only']}")
    return '\n'.join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run-dir', required=True)
    ap.add_argument('--json')
    a = ap.parse_args(argv)
    try:
        t = trace(a.run_dir)
    except TraceError as exc:
        print(f'BLOCKED  {exc}')
        return 2
    print(render(t))
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(t, indent=2) + '\n')
        print(f'\nfull trace written to {a.json}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
