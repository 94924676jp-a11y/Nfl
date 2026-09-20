"""capture_validation's PASS must mean the captures were validated.

Today it does not, and these tests pin exactly that so the gap cannot close by
accident or widen unnoticed.

TWO DEFECTS, AND THEY ARE DIFFERENT

DK-3 -- `capture_validation` iterates the source set it is HANDED. It checks
each supplied entry for a sha256, a `retrieved_at` no later than `written_at`,
registry membership and schema. It never asks whether a REQUIRED source is
absent. So a caller supplying one synthetic entry gets PASS[INPUTS_VALIDATED]
for the whole stage, and a caller supplying nothing gets SOURCE_MISSING -- the
two outcomes differ by the caller's choice, not by the captures.

DK-4 -- the only slate driver in the repository,
`nfl/production/rehearsal/run_slate.py`, supplies exactly that one synthetic
entry: sha256 = 'b' * 64, retrieved_at fixed. It is declared REHEARSAL ONLY and
sets `dry_run=True` in the call, which is the honest consequence of the
placeholder rather than an unrelated choice. There is no production fixture
assembler, so there is no caller that can satisfy this stage with evidence.

WHAT THESE TESTS DO NOT CLAIM. The football layers below the stage read real
captures through `vintage_selector`, with real capture ids. The numbers rest on
real evidence; the PROVENANCE RECORD does not. A test that conflated those
would be measuring the wrong thing.

These are CHARACTERISATION tests. They assert the defect as it stands. When the
fixture assembler lands, they fail -- and that failure is the signal to update
them, deliberately, in the same commit that fixes the behaviour.
"""
from __future__ import annotations

import argparse
import ast
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_P, _F = 0, 0


def ok(cond, what):
    global _P, _F
    if cond:
        _P += 1
        print(f'  ok     {what}')
    else:
        _F += 1
        print(f'  FAIL   {what}')


def _args(**kw):
    base = dict(season=2026, week=2, game_id='2026_02_CAR_ATL', arm='A',
                written_at='2026-09-20T05:00:00Z', seed=20260908,
                dry_run=False, fixtures=None,
                model_configuration='PRODUCTION_BASELINE')
    base.update(kw)
    return argparse.Namespace(**base)


def test_driver_supplies_a_placeholder_hash():
    """The literal is READ OUT OF THE SOURCE, not recalled."""
    p = _REPO / 'nfl' / 'production' / 'rehearsal' / 'run_slate.py'
    tree = ast.parse(p.read_text())
    found = []
    for node in ast.walk(tree):
        # `'b' * 64` is a BinOp over a constant, so the string never appears
        # literally in the file and a grep for sixty-four b's finds nothing.
        # NOT ast.literal_eval: it accepts only + and - between numbers, so
        # it raises on `'b' * 64` and an `except: continue` around it silently
        # finds NOTHING -- which is what the first version of this test did,
        # and it reported the absence of a placeholder that is plainly there.
        # The multiplication is evaluated by hand instead.
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
            l, r = node.left, node.right
            if not (isinstance(l, ast.Constant) and isinstance(r, ast.Constant)):
                continue
            if not (isinstance(l.value, str) and isinstance(r.value, int)):
                continue
            v = l.value * r.value
            if len(v) == 64 and len(set(v)) == 1:
                found.append(v)
    ok(found == ['b' * 64],
       "run_slate.py builds its source sha256 as 'b' * 64 -- a placeholder, "
       'and the ONLY source it declares')

    ok("REHEARSAL ONLY" in (ast.get_docstring(tree) or ''),
       'and the module says REHEARSAL ONLY in its own docstring, so the '
       'placeholder and the quarantine are one decision')

    sets_dry = any(
        isinstance(n, ast.keyword) and n.arg == 'dry_run'
        and isinstance(n.value, ast.Constant) and n.value.value is True
        for n in ast.walk(tree))
    ok(sets_dry,
       'and it passes dry_run=True in the call itself: there is no flag a '
       'caller can clear')


def test_capture_validation_has_no_required_source_check():
    """PASS on a set of one fabricated entry. This is DK-3, demonstrated."""
    from nfl.production import run_forecast as RUN

    fx = {'kickoff_utc': '2026-09-20T17:00:00Z',
          'source_hashes': {'schedules': {
              'sha256': 'b' * 64,
              'retrieved_at': '2026-09-08T12:00:00Z'}},
          'players': [], 'team_ids': ['CAR', 'ATL'],
          'qb_slate': {'prospective': True}, 'qb_draws': 8,
          'team_volume': True, 'distributions': {}}
    s = RUN.build(_args(out_dir='/tmp/claude-0/cvtest'), dict(fx))
    st = {r['stage']: r for r in s['stages']}
    cv = st.get('capture_validation')
    ok(cv is not None, 'the run reports a capture_validation stage')
    ok(cv and cv['state'] == 'PASS' and cv['code'] == 'INPUTS_VALIDATED',
       'ONE fabricated source entry passes capture_validation outright: '
       f"state={cv and cv['state']} code={cv and cv['code']}. The stage "
       'validates what it is handed and never asks what is missing')


def test_direct_entrypoint_without_fixtures_refuses():
    """DK-4's other half: with no fixtures there is nothing to validate."""
    from nfl.production import run_forecast as RUN

    s = RUN.build(_args(out_dir='/tmp/claude-0/cvtest'), {})
    st = {r['stage']: r for r in s['stages']}
    cv = st.get('capture_validation')
    ok(cv and cv['state'] == 'BLOCKED' and cv['code'] == 'SOURCE_MISSING',
       'run_forecast.build with no fixtures refuses SOURCE_MISSING at '
       f"capture_validation: state={cv and cv['state']} "
       f"code={cv and cv['code']}")
    ok(s['status'] == 'REFUSED',
       'and the run as a whole is REFUSED, so no layer below it executes')


def test_the_two_outcomes_differ_only_by_the_caller():
    """The point of DK-3 stated as a single comparison.

    Same captures on disk, same week, same clock. One caller passes, one
    refuses. Nothing about the CAPTURES distinguishes them.
    """
    from nfl.production import run_forecast as RUN

    fx = {'kickoff_utc': '2026-09-20T17:00:00Z',
          'source_hashes': {'schedules': {
              'sha256': 'b' * 64,
              'retrieved_at': '2026-09-08T12:00:00Z'}},
          'players': [], 'team_ids': ['CAR', 'ATL'],
          'qb_slate': {'prospective': True}, 'qb_draws': 8,
          'team_volume': True, 'distributions': {}}
    a = RUN.build(_args(out_dir='/tmp/claude-0/cvtest'), dict(fx))
    b = RUN.build(_args(out_dir='/tmp/claude-0/cvtest'), {})
    ca = {r['stage']: r for r in a['stages']}['capture_validation']
    cb = {r['stage']: r for r in b['stages']}['capture_validation']
    ok(ca['state'] != cb['state'],
       f"the same captures yield {ca['state']} and {cb['state']} depending "
       'only on what the caller declares -- which is what makes this stage a '
       'statement about the caller rather than about the captures')


def main():
    for t in (test_driver_supplies_a_placeholder_hash,
              test_capture_validation_has_no_required_source_check,
              test_direct_entrypoint_without_fixtures_refuses,
              test_the_two_outcomes_differ_only_by_the_caller):
        print(f'== {t.__name__}')
        t()
    print(f'\n{_P} passed, {_F} failed')
    return 1 if _F else 0


if __name__ == '__main__':
    sys.exit(main())
