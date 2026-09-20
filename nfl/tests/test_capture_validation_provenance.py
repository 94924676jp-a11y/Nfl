"""capture_validation's PASS must mean the captures were validated.

It did not, in two independent ways. Both are now closed and these tests hold
them closed.

DK-3 -- the stage iterated the source set it was HANDED and never asked
whether a source the run actually reads was ABSENT, so one entry returned
PASS[INPUTS_VALIDATED] for the whole stage. It now derives its required set
from `vintage_selector.FAMILIES` -- the existing "DECLARED, NOT DISCOVERED"
list of every perishable source the production layers select a vintage from --
and refuses REQUIRED_SOURCE_NOT_DECLARED naming each missing one. Derived
rather than hand-written, because a hand-written list goes stale the moment a
family is added, and goes stale silently.

DK-4 -- nothing asked whether the declared BYTES existed. Four fabricated
hashes for the four required sources passed everything. Every declared sha256
must now match a PASS capture in the vintage manifest, and the blob is
reopened and rehashed rather than trusted. `fixture_assembler` builds a real
fixture from the same selector call the football layers make, so the validated
set and the consumed set are finally the same set; they were disjoint before,
which is why nothing ever complained.

WHAT THESE TESTS ASSERT THAT IS EASY TO GET WRONG

A DECLARED DRY RUN MAY STILL USE SYNTHETIC CAPTURES, and that is not a bypass
left open for convenience. `--dry-run` already means "historical fixture run;
NEVER prospective evidence"; such a run is stamped prospective_eligible=false
and refused publication. A run that wants to feed the engine synthetic inputs
IS a dry run, and saying so out loud is the honest form of it. What is no
longer possible is a run that consumes fabricated captures WITHOUT carrying
that label -- and `test_a_dry_run_says_so_on_the_record` checks that the
exemption is announced on the stage record rather than taken silently.

THE PLACEHOLDER IS GONE FROM `run_slate.py` and the AST test proves it rather
than grepping: `'b' * 64` never appears literally in a file, so a text search
for sixty-four b's finds nothing and would have reported the placeholder
absent while it sat there. An earlier version of this very test used
`ast.literal_eval` on that BinOp, which accepts only + and - between numbers,
raised, and was swallowed by an except-continue -- it reported the absence of
a placeholder that was plainly there. The multiplication is evaluated by hand.
"""
from __future__ import annotations

import argparse
import ast
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production import fixture_assembler as FA                 # noqa: E402
from nfl.production import run_forecast as RUN                     # noqa: E402
from sportsplatform.governance.outcome import State                # noqa: E402

_P, _F = 0, 0
_CACHE = {}

CUT = '2026-09-20T05:00:00Z'


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
                written_at=CUT, seed=20260908,
                dry_run=False, fixtures=None,
                out_dir='/tmp/claude-0/cvtest',
                model_configuration='PRODUCTION_BASELINE')
    base.update(kw)
    return argparse.Namespace(**base)


def _base_fx(**over):
    f = {'kickoff_utc': '2026-09-20T17:00:00Z',
         'players': [], 'team_ids': ['CAR', 'ATL'],
         'qb_slate': {'prospective': True}, 'qb_draws': 8,
         'team_volume': True, 'distributions': {}}
    f.update(over)
    return f


def _fake_hashes():
    return {n: {'sha256': 'b' * 64, 'retrieved_at': '2026-09-08T12:00:00Z'}
            for n in RUN.required_capture_sources()['required']}


def _assembled():
    if 'asm' not in _CACHE:
        _CACHE['asm'] = FA.assemble(CUT)
    return _CACHE['asm']


def _cv(args, fx):
    s = RUN.build(args, dict(fx))
    return {r['stage']: r for r in s['stages']}.get('capture_validation'), s


def _long_placeholders(path):
    """Single-character string constants of length 64, built by multiplication.

    NOT ast.literal_eval: it accepts only + and - between numbers, so it raises
    on `'b' * 64` and an except-continue around it silently finds nothing.
    """
    found = []
    for node in ast.walk(ast.parse(pathlib.Path(path).read_text())):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
            l, r = node.left, node.right
            if not (isinstance(l, ast.Constant) and isinstance(r, ast.Constant)):
                continue
            if not (isinstance(l.value, str) and isinstance(r.value, int)):
                continue
            v = l.value * r.value
            if len(v) == 64 and len(set(v)) == 1:
                found.append((v, node.lineno))
    return found


# ======================================================================= DK-4
def test_the_placeholder_is_gone_from_the_slate_driver():
    p = _REPO / 'nfl' / 'production' / 'rehearsal' / 'run_slate.py'
    ok(_long_placeholders(p) == [],
       f'run_slate.py contains no 64-character placeholder hash: '
       f'{_long_placeholders(p)}')

    tree = ast.parse(p.read_text())
    # `from nfl.production import fixture_assembler as FA` puts the package
    # in `n.module` and the module in `a.name`, so collecting only `n.module`
    # reports the import absent when it is right there.
    imports = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import)
               for a in n.names}
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module:
            imports.add(n.module)
            imports |= {f'{n.module}.{a.name}' for a in n.names}
    ok('nfl.production.fixture_assembler' in imports,
       f'and it imports the fixture assembler instead: '
       f'{sorted(i for i in imports if "fixture" in i) or imports}')

    sets_dry = any(
        isinstance(n, ast.keyword) and n.arg == 'dry_run'
        and isinstance(n.value, ast.Constant) and n.value.value is True
        for n in ast.walk(tree))
    ok(sets_dry,
       'and it STILL sets dry_run=True. Removing the placeholder makes this '
       'driver honest about its inputs; it does not promote a module whose '
       'own docstring says REHEARSAL ONLY into the production path')


def test_the_assembler_measures_hashes_rather_than_copying_them():
    o = _assembled()
    ok(o.state is State.PASS,
       f'the fixture assembles at {CUT}: {o.state.name}[{o.code}]')
    if o.state is not State.PASS:
        return
    det = (o.evidence or {})['detail_by_source']
    ok(sorted(o.value) == RUN.required_capture_sources()['required'],
       f'covering exactly the required sources: {sorted(o.value)}')
    for name, d in sorted(det.items()):
        ok(d['hash_measured_here'] and d['manifest_agrees'] is True,
           f'{name}: {d["blob"]} reopened and hashed here, and the manifest '
           f'record agrees')
        ok(pathlib.Path(_REPO / d['blob']).exists(),
           f'{name}: the blob it names is on disk')
    ok(all(len(v['sha256']) == 64 for v in o.value.values()),
       'every emitted hash is a full sha256, not a content-address prefix')


def test_fabricated_hashes_are_refused_on_a_real_run():
    cv, s = _cv(_args(), _base_fx(source_hashes=_fake_hashes()))
    ok(cv and cv['state'] == 'BLOCKED'
       and cv['code'] == 'DECLARED_CAPTURES_UNVERIFIED',
       f'four fabricated hashes for the four required sources are REFUSED: '
       f"{cv and cv['state']} {cv and cv['code']}")
    for n in RUN.required_capture_sources()['required']:
        ok(cv and n in cv['detail'],
           f'and the refusal names {n} rather than returning a bare code')
    ok(s['status'] == 'REFUSED',
       'and the run as a whole refuses, so no layer reads anything')


def test_a_dry_run_says_so_on_the_record():
    """The exemption is announced, not taken silently."""
    cv, s = _cv(_args(dry_run=True), _base_fx(source_hashes=_fake_hashes()))
    ok(cv and cv['state'] == 'PASS',
       f'a DECLARED dry run may still use synthetic captures: '
       f"{cv and cv['state']}")
    gov = [g for g in (cv or {}).get('governance') or []
           if g.get('layer') == 'capture_validation']
    ok(len(gov) == 1 and gov[0].get('bytes_verified') is False,
       f'and the stage record says the bytes were NOT verified: '
       f'{gov and gov[0].get("bytes_verified")}')
    ok(gov and 'DRY_RUN' in gov[0]['governance'],
       f'naming the reason: {gov and gov[0]["governance"]!r}')
    ok(s.get('prospective_eligible') is False,
       f'and the run is stamped prospective_eligible=false, which is what '
       f'makes the exemption safe: {s.get("prospective_eligible")}')


def test_an_assembled_fixture_passes_and_the_pass_says_why():
    o = _assembled()
    if o.state is not State.PASS:
        ok(False, 'the fixture must assemble for this test to mean anything')
        return
    cv, _s = _cv(_args(), _base_fx(source_hashes=dict(o.value)))
    ok(cv and cv['state'] == 'PASS' and cv['code'] == 'INPUTS_VALIDATED',
       f'a fixture built from the vintage manifest passes: '
       f"{cv and cv['state']} {cv and cv['code']}")
    gov = [g for g in (cv or {}).get('governance') or []
           if g.get('layer') == 'capture_validation']
    ok(len(gov) == 1 and gov[0].get('bytes_verified') is True,
       'and the PASS records that the declared bytes WERE verified')
    ok(gov and 'VINTAGE_MANIFEST' in gov[0]['governance'],
       f'against the vintage manifest, named: {gov and gov[0]["governance"]!r}')
    ok(gov and gov[0].get('required') == RUN.required_capture_sources()[
        'required'],
       'and it names the required set it checked, so a reader need not '
       'recompute it')


def test_one_tampered_byte_is_caught():
    """The hash is checked against the BYTES, not against another record."""
    o = _assembled()
    if o.state is not State.PASS:
        ok(False, 'need an assembled fixture')
        return
    src = {k: dict(v) for k, v in o.value.items()}
    victim = sorted(src)[0]
    h = src[victim]['sha256']
    src[victim]['sha256'] = ('0' if h[0] != '0' else '1') + h[1:]
    cv, _s = _cv(_args(), _base_fx(source_hashes=src))
    ok(cv and cv['state'] == 'BLOCKED'
       and cv['code'] == 'DECLARED_CAPTURES_UNVERIFIED',
       f'flipping one character of one real hash is refused: '
       f"{cv and cv['state']} {cv and cv['code']}")
    ok(cv and victim in cv['detail'],
       f'and the refusal names {victim}, the one that was altered')


# ======================================================================= DK-3
def test_capture_validation_requires_the_sources_the_layers_select():
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

    one = {'schedules': {'sha256': 'b' * 64,
                         'retrieved_at': '2026-09-08T12:00:00Z'}}
    cv, _s = _cv(_args(), _base_fx(source_hashes=one))
    ok(cv and cv['state'] == 'BLOCKED'
       and cv['code'] == 'REQUIRED_SOURCE_NOT_DECLARED',
       f'declaring one of four required sources is refused BEFORE the bytes '
       f"are even looked at: {cv and cv['state']} {cv and cv['code']}")
    for name in ('depth_charts', 'injuries', 'weekly_rosters'):
        ok(cv and name in cv['detail'],
           f'and the refusal NAMES {name} rather than returning a bare code')


def test_direct_entrypoint_without_fixtures_refuses():
    cv, s = _cv(_args(), {})
    ok(cv and cv['state'] == 'BLOCKED' and cv['code'] == 'SOURCE_MISSING',
       f'no fixtures at all refuses SOURCE_MISSING: '
       f"{cv and cv['state']} {cv and cv['code']}")
    ok(cv and 'depth_charts' in cv['detail'],
       'and names what the run must declare, so a caller is told the '
       'requirement rather than left to guess it')
    ok(s['status'] == 'REFUSED', 'and the run as a whole is REFUSED')


def test_well_formedness_is_checked_before_completeness():
    """Order matters: every per-entry refusal must stay reachable.

    Completeness first would have masked SOURCE_TOO_LATE, SCHEMA_DRIFT,
    RAW_HASH_MISMATCH and UNAUTHORIZED_INPUT behind one code.
    """
    late = {'schedules': {'sha256': 'b' * 64,
                          'retrieved_at': '2026-09-21T00:00:00Z'}}
    cv, _s = _cv(_args(), _base_fx(source_hashes=late))
    ok(cv and cv['code'] == 'SOURCE_TOO_LATE',
       f'one entry retrieved after written_at still reports SOURCE_TOO_LATE, '
       f'not the completeness code: {cv and cv["code"]}')

    unauth = {'some_vendor_feed': {'sha256': 'b' * 64,
                                   'retrieved_at': '2026-09-08T12:00:00Z'}}
    cv, _s = _cv(_args(), _base_fx(source_hashes=unauth))
    ok(cv and cv['code'] == 'UNAUTHORIZED_INPUT',
       f'and an unregistered source still reports UNAUTHORIZED_INPUT: '
       f'{cv and cv["code"]}')


def test_the_two_refusals_say_different_things():
    one = {'schedules': {'sha256': 'b' * 64,
                         'retrieved_at': '2026-09-08T12:00:00Z'}}
    a, _ = _cv(_args(), _base_fx(source_hashes=one))
    b, _ = _cv(_args(), {})
    ok(a['state'] == b['state'] == 'BLOCKED',
       f'both callers refuse: {a["state"]} and {b["state"]}')
    ok(a['code'] == 'REQUIRED_SOURCE_NOT_DECLARED'
       and b['code'] == 'SOURCE_MISSING',
       f'and the codes distinguish what each got wrong: {a["code"]} vs '
       f'{b["code"]}. A stage that flattened them would be less diagnostic, '
       f'not more strict')


def main():
    for t in (test_the_placeholder_is_gone_from_the_slate_driver,
              test_the_assembler_measures_hashes_rather_than_copying_them,
              test_fabricated_hashes_are_refused_on_a_real_run,
              test_a_dry_run_says_so_on_the_record,
              test_an_assembled_fixture_passes_and_the_pass_says_why,
              test_one_tampered_byte_is_caught,
              test_capture_validation_requires_the_sources_the_layers_select,
              test_direct_entrypoint_without_fixtures_refuses,
              test_well_formedness_is_checked_before_completeness,
              test_the_two_refusals_say_different_things):
        print(f'== {t.__name__}')
        t()
    print(f'\nPASSED {_P} FAILED {_F}')
    return 1 if _F else 0


if __name__ == '__main__':
    sys.exit(main())
