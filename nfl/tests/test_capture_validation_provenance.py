"""capture_validation's PASS must mean the captures were validated.

Today it does not, and these tests pin exactly that so the gap cannot close by
accident or widen unnoticed.

TWO DEFECTS, AND THEY ARE DIFFERENT. ONE IS NOW FIXED.

DK-3 -- FIXED in the same commit that rewrote this file. `capture_validation`
used to iterate the source set it was HANDED and never ask whether a source
the run actually reads was ABSENT, so one synthetic entry returned
PASS[INPUTS_VALIDATED] for the whole stage. It now derives its required set
from `vintage_selector.FAMILIES` -- the existing "DECLARED, NOT DISCOVERED"
list of every perishable source the production layers select a vintage from --
intersected with the fetched-source registry, and refuses
REQUIRED_SOURCE_NOT_DECLARED naming each missing one. The basis is derived
rather than hand-written precisely because a hand-written list goes stale the
moment a family is added, and goes stale silently.

DK-4 -- STILL OPEN, and these tests still characterise it. The only slate
driver in the repository, `nfl/production/rehearsal/run_slate.py`, supplies
one entry whose sha256 is 'b' * 64. DK-3's fix now refuses that run for
declaring only `schedules`, which is progress and is not the whole defect: a
caller that declared all four sources with four fabricated hashes would still
pass. This stage checks that every required source was DECLARED and that each
declaration is WELL FORMED. It does not check that the declared bytes exist.
Until a production fixture assembler reads the vintage manifest and emits true
hashes, no caller can satisfy this stage with evidence.

WHAT THESE TESTS DO NOT CLAIM. The football layers below the stage read real
captures through `vintage_selector`, with real capture ids. The numbers rest
on real evidence; the PROVENANCE RECORD does not. A test that conflated those
would be measuring the wrong thing.

The DK-4 tests are CHARACTERISATION tests: they assert the defect as it
stands. When the fixture assembler lands they fail, and that failure is the
signal to update them, deliberately, in the same commit that fixes the
behaviour.
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


def test_capture_validation_requires_the_sources_the_layers_select():
    """DK-3, fixed. One fabricated entry no longer passes the stage."""
    from nfl.production import run_forecast as RUN

    req = RUN.required_capture_sources()
    ok(req['required'] == ['depth_charts', 'injuries', 'schedules',
                           'weekly_rosters'],
       f'the required set is {req["required"]}, derived from '
       f'vintage_selector.FAMILIES rather than written by hand')
    ok(req['families_not_registered_sources'] == [],
       'and every declared family is an authorized capture source, so '
       'nothing in the requirement is unfetchable')
    for name in ('official_inactives', 'official_injury_report',
                 'espn_injuries_json'):
        ok(req['not_required_and_why'].get(name),
           f'{name} is excluded WITH A STATED REASON rather than by omission')

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
    ok(cv and cv['state'] == 'BLOCKED'
       and cv['code'] == 'REQUIRED_SOURCE_NOT_DECLARED',
       f'the exact source set run_slate supplies is now REFUSED: '
       f"state={cv and cv['state']} code={cv and cv['code']}")
    for name in ('depth_charts', 'injuries', 'weekly_rosters'):
        ok(cv and name in cv['detail'],
           f'and the refusal NAMES {name} rather than returning a bare code')


def test_a_pass_says_what_it_did_not_check():
    """The half DK-3 does not fix, stated on the PASS and not only in prose.

    Four fabricated hashes for the four required sources still pass. That is
    DK-4, and a PASS that did not say so would be read as more than it is.
    """
    from nfl.production import run_forecast as RUN

    fx = {'kickoff_utc': '2026-09-20T17:00:00Z',
          'source_hashes': {n: {'sha256': 'b' * 64,
                                'retrieved_at': '2026-09-08T12:00:00Z'}
                            for n in RUN.required_capture_sources()['required']},
          'players': [], 'team_ids': ['CAR', 'ATL'],
          'qb_slate': {'prospective': True}, 'qb_draws': 8,
          'team_volume': True, 'distributions': {}}
    s = RUN.build(_args(out_dir='/tmp/claude-0/cvtest'), dict(fx))
    st = {r['stage']: r for r in s['stages']}
    cv = st.get('capture_validation')
    ok(cv and cv['state'] == 'PASS',
       f'four fabricated hashes for the four required sources still pass: '
       f"{cv and cv['state']} {cv and cv['code']}. DK-3 closed the "
       f'missing-source hole and did not close this one')
    # READ OFF THE STAGE RECORD, with no fallback. An earlier draft of this
    # test substituted the expected string when the record did not carry one,
    # which made the assertion unfailable and would have hidden the very gap
    # it is here to prove -- evidence the pipeline does not copy into the
    # record dies silently.
    gov = [g for g in (cv or {}).get('governance') or []
           if g.get('layer') == 'capture_validation']
    ok(len(gov) == 1,
       f'the PASS carries exactly one capture_validation governance record: '
       f'{len(gov)}')
    txt = gov[0]['governance'] if gov else ''
    ok('NOT checked' in txt and 'DK-4' in txt,
       f'and it declares its own scope -- declaration completeness and '
       f'well-formedness, NOT the existence of the declared bytes: {txt!r}')
    ok(gov and gov[0].get('required') == RUN.required_capture_sources()[
        'required'],
       'and it names the required set it checked, so a reader need not '
       'recompute it')


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


def test_both_callers_now_refuse_and_for_different_reasons():
    """What DK-3 changed, stated as the comparison it replaces.

    This test used to assert the defect: the same captures on disk yielded
    PASS or BLOCKED depending only on what the caller declared, which made the
    stage a statement about its caller. Both callers now refuse, and the two
    refusals say DIFFERENT things -- nothing declared, versus three of four
    required sources undeclared. A refusal that distinguishes those is
    diagnostic; one that flattened them would not be.
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
    ok(ca['state'] == cb['state'] == 'BLOCKED',
       f'both callers refuse: {ca["state"]} and {cb["state"]}')
    ok(ca['code'] == 'REQUIRED_SOURCE_NOT_DECLARED'
       and cb['code'] == 'SOURCE_MISSING',
       f'and the codes distinguish what each got wrong: {ca["code"]} vs '
       f'{cb["code"]}')
    ok('depth_charts' in cb['detail'],
       'the empty-set refusal also names what the run must declare, so a '
       'caller is told the requirement rather than left to guess it')


def main():
    for t in (test_driver_supplies_a_placeholder_hash,
              test_capture_validation_requires_the_sources_the_layers_select,
              test_a_pass_says_what_it_did_not_check,
              test_direct_entrypoint_without_fixtures_refuses,
              test_both_callers_now_refuse_and_for_different_reasons):
        print(f'== {t.__name__}')
        t()
    print(f'\n{_P} passed, {_F} failed')
    return 1 if _F else 0


if __name__ == '__main__':
    sys.exit(main())
