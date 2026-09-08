"""Stage 16: the routes adapter must fail closed, and stay closed."""
import os, pathlib, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from sportsplatform.governance.outcome import Outcome, State      # noqa: E402
from nfl.adapters import routes_source as RS                      # noqa: E402
from nfl.tests.bypass import assert_guard_is_load_bearing         # noqa: E402

PASSED = FAILED = 0


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1; print(f'  ok   {label}')
    else:
        FAILED += 1; print(f'  FAIL {label}' + (f'  [{detail}]' if detail else ''))


class Full:
    name = 'test_provider'; licence_id = 'L-1'
    permits_model_training = True; permits_local_retention = True
    permits_derived_output_ownership = True
    def routes_run(self, s, w):
        return Outcome.ok('ROUTES', value={'p1': 30})


def test_a_fails_closed():
    print('\nA. no provider, no data')
    RS.clear_provider()
    o = RS.routes_run(2026, 1)
    check('routes_run is BLOCKED with no provider',
          o.state is State.BLOCKED
          and o.code == 'NO_LICENSED_ROUTES_PROVIDER', o.code)
    check('  and it returns no data of any kind', o.value is None
          or o.value == {} or not o.value)
    src = pathlib.Path(RS.__file__).read_text()
    for bad in ('sample_rows', 'FAKE', 'example_data', 'stub_routes'):
        check(f'  the module ships no {bad}', bad not in src)
    check('  and names no vendor endpoint',
          'http' not in src.lower() or 'https://' not in src)


def test_b_rights_are_not_inferred_from_silence():
    print('\nB. a provider must DECLARE its rights')
    class NoTrain(Full):
        permits_model_training = False
    o = RS.register_provider(NoTrain())
    check('a provider without model-training rights is refused',
          o.state is State.BLOCKED
          and o.code == 'PROVIDER_RIGHTS_INSUFFICIENT', o.code)
    class NoRetain(Full):
        permits_local_retention = False
    check('  without retention rights, refused',
          RS.register_provider(NoRetain()).state is State.BLOCKED)
    class NoOwn(Full):
        permits_derived_output_ownership = False
    check('  without derived-output ownership, refused',
          RS.register_provider(NoOwn()).state is State.BLOCKED)
    class NoLic(Full):
        licence_id = None
    check('  unlicensed, refused',
          RS.register_provider(NoLic()).code == 'PROVIDER_UNLICENSED')
    check('  and after all those refusals the adapter is STILL closed',
          RS.routes_run(2026, 1).state is State.BLOCKED)


def test_c_a_full_provider_opens_it_and_clearing_closes_it():
    print('\nC. the interface works when rights are actually supplied')
    o = RS.register_provider(Full())
    check('a fully-rights-declaring licensed provider registers',
          o.state is State.PASS, o.code)
    check('  and routes_run then returns its data',
          RS.routes_run(2026, 1).state is State.PASS)
    RS.clear_provider()
    check('  and clearing it closes the adapter again',
          RS.routes_run(2026, 1).state is State.BLOCKED)


def test_d_near_miss_fields_may_not_be_substituted():
    print('\nD. nflverse.route is not routes run')
    for s in ('nflverse.route', 'pbp_participation.route', 'ngs_air_yards'):
        o = RS.assert_not_a_forbidden_substitute(s)
        check(f'{s} may not be adapted in as routes run',
              o.state is State.FAIL
              and o.code == 'FORBIDDEN_ROUTES_SUBSTITUTE', o.code)
    check('  and the reason is recorded, not just the refusal',
          'no player id' in RS.FORBIDDEN_SOURCES['nflverse.route'])
    o = RS.assert_not_a_forbidden_substitute('a_licensed_vendor')
    check('  a genuine source is not blanket-refused', o.state is State.PASS)


def test_e_guard_deletion():
    print('\nE. guard-deletion proof')
    RS.clear_provider()

    def run():
        return RS.routes_run(2026, 1)
    assert_guard_is_load_bearing(
        run=run, module_path='nfl.adapters.routes_source', attr='routes_run',
        caught=lambda o: o.state is State.BLOCKED,
        returns=Outcome.ok('STUB', value={'p1': 99}))
    check('routes_run is load-bearing -- bypassed, unlicensed routes data '
          'flows with no provider registered', True)


if __name__ == '__main__':
    test_a_fails_closed()
    test_b_rights_are_not_inferred_from_silence()
    test_c_a_full_provider_opens_it_and_clearing_closes_it()
    test_d_near_miss_fields_may_not_be_substituted()
    test_e_guard_deletion()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
