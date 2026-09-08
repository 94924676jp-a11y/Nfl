"""Stage 1 adversarial tests for the frozen-experiment identity gate.

Every probe below describes a real way a future prospective run could end up
standing on different bytes while still calling itself the frozen candidate.
Each one must be REFUSED or relabelled, and sections J and K delete the guards
to prove the refusals are the guards' doing.
"""
import copy, json, os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import identity as I                                           # noqa: E402

P = F = 0


def check(l, c, d=''):
    global P, F
    if c:
        P += 1
        print(f'  ok   {l}')
    else:
        F += 1
        print(f'  FAIL {l}  {d}')


SPEC, SPEC_SHA = I.load_spec()


def good_descriptor():
    """A run that genuinely is the frozen experiment."""
    return {
        'derived_artifacts': {k: v['sha256']
                              for k, v in SPEC['derived_artifacts'].items()},
        'leaf_inputs': dict(SPEC['leaf_inputs']),
        'source_code': dict(SPEC['source_code']),
        'panel_identity': copy.deepcopy(SPEC['panel_identity']),
        'dtype_contract': dict(SPEC['dtype_contract']),
        'seed_protocol': dict(SPEC['seed_protocol']),
        'draw_protocol': copy.deepcopy(SPEC['draw_protocol']),
        'solver': dict(SPEC['solver']),
        'feature_set': copy.deepcopy(SPEC['feature_set']),
        'consumed_seasons': [2022, 2023, 2024, 2025],
    }


def test_the_matching_case():
    print('\nA. a genuine match is confirmed, and confirms only identity')
    r = I.verify(good_descriptor())
    check('the frozen run is CONFIRMED', r['label'] == I.CONFIRMED, r.get('code'))
    check('  and the spec hash is reported, not assumed',
          r['spec_sha256'] == SPEC_SHA and len(r['spec_sha256']) == 64)
    check('  and it says confirmation is not promotion',
          r.get('not_promoted') is True and 'does not promote' in r['detail'])


def _mutate(fn):
    d = good_descriptor()
    fn(d)
    return I.verify(d)


def test_stale_and_wrong_artifacts():
    print('\nB. a stale or wrong derived artifact')
    k = sorted(SPEC['derived_artifacts'])[0]
    r = _mutate(lambda d: d['derived_artifacts'].__setitem__(k, '0' * 64))
    check('a wrong artifact hash is DIFFERENT_INPUT_GENERATION',
          r['label'] == I.DIFFERENT, r['label'])
    check('  naming the artifact',
          any(m['field'] == k for m in r['mismatches']), r['mismatches'][:1])
    r = _mutate(lambda d: d['derived_artifacts'].pop(k))
    check('a MISSING artifact is a mismatch, never a pass',
          r['label'] == I.DIFFERENT
          and any(m['actual'] is None for m in r['mismatches']))
    lk = sorted(SPEC['leaf_inputs'])[0]
    r = _mutate(lambda d: d['leaf_inputs'].__setitem__(lk, 'f' * 64))
    check('a stale leaf input is caught', r['label'] == I.DIFFERENT)


def test_row_ordering_and_dtype():
    print('\nC. same numbers, different arrangement')
    ev = sorted(SPEC['panel_identity'])[0]
    r = _mutate(lambda d: d['panel_identity'][ev].__setitem__(
        'row_order_sha256', 'a' * 64))
    check('a different row ordering is a different generation',
          r['label'] == I.DIFFERENT,
          [m['field'] for m in r['mismatches']][:2])
    r = _mutate(lambda d: d['panel_identity'][ev].__setitem__('n', 9999))
    check('a different row COUNT is caught too', r['label'] == I.DIFFERENT)
    r = _mutate(lambda d: d['dtype_contract'].__setitem__('W', 'float64'))
    check('float64 draws are not the frozen float32 experiment',
          r['label'] == I.DIFFERENT)
    check('  and the gate says which field',
          any(m['field'] == 'W' for m in
              I.verify({**good_descriptor(),
                        'dtype_contract': {**SPEC['dtype_contract'],
                                           'W': 'float64'}})['mismatches']))


def test_seed_draw_and_solver():
    print('\nD. a different seed or solver is a different experiment')
    r = _mutate(lambda d: d['seed_protocol'].__setitem__('base_seed', 1))
    check('a different base seed is caught', r['label'] == I.DIFFERENT)
    r = _mutate(lambda d: d['seed_protocol'].__setitem__('weights', 'SEED+1'))
    check('a different weight-draw seed is caught', r['label'] == I.DIFFERENT)
    r = _mutate(lambda d: d['draw_protocol'].__setitem__(
        'shared_draw_sequence_with_control', False))
    check('losing the shared draw sequence is caught', r['label'] == I.DIFFERENT)
    r = _mutate(lambda d: d['solver'].__setitem__('tolerance_abs', 1e-6))
    check('a loosened solver tolerance is caught', r['label'] == I.DIFFERENT)
    r = _mutate(lambda d: d['solver'].__setitem__('iterations', 20))
    check('a shortened bisection is caught', r['label'] == I.DIFFERENT)


def test_upstream_identity_and_features():
    print('\nE. changed upstream code, or a changed feature set')
    k = sorted(SPEC['source_code'])[0]
    r = _mutate(lambda d: d['source_code'].__setitem__(k, 'b' * 64))
    check('a changed upstream module is caught', r['label'] == I.DIFFERENT,
          [m['field'] for m in r['mismatches']][:2])
    def add_feat(d):
        d['feature_set'] = copy.deepcopy(SPEC['feature_set'])
        d['feature_set']['blocks']['A'] = list(
            d['feature_set']['blocks']['A']) + ['g_sneaky_extra']
    r = _mutate(add_feat)
    check('an extra feature is caught', r['label'] == I.DIFFERENT)
    def drop_block(d):
        d['feature_set'] = copy.deepcopy(SPEC['feature_set'])
        d['feature_set']['blocks'].pop('C')
    check('a dropped block is caught', _mutate(drop_block)['label'] == I.DIFFERENT)


def test_silence_is_not_agreement():
    print('\nF. an undeclared component is refused, not assumed to match')
    for g in I.REQUIRED_GROUPS:
        r = _mutate(lambda d, g=g: d.pop(g))
        check(f'omitting {g} is REFUSED',
              r['label'] == I.REFUSED and r['code'] == 'DESCRIPTOR_INCOMPLETE',
              r.get('code'))
        if g == 'solver':
            check('  and it explains that silence is not a match',
                  'Silence is refused' in r['detail'])


def test_forbidden_2026():
    print('\nG. a run that touched 2026 outcomes is inadmissible')
    r = _mutate(lambda d: d.__setitem__('consumed_seasons',
                                        [2023, 2024, 2025, 2026]))
    check('consuming 2026 is REFUSED outright',
          r['label'] == I.REFUSED and r['code'] == 'FORBIDDEN_SEASON_CONSUMED',
          r.get('code'))
    check('  and it is refused rather than merely relabelled',
          r['label'] != I.DIFFERENT)
    r = _mutate(lambda d: d.__setitem__('consumed_seasons', 'all of them'))
    check('a malformed season declaration is REFUSED',
          r['code'] == 'CONSUMED_SEASONS_MALFORMED')


def test_a_typed_hash_is_still_checked():
    print('\nH. a manually typed frozen value does not become truth')
    real = SPEC['derived_artifacts']['panel_enriched.pkl']['sha256']
    typo = real[:-1] + ('0' if real[-1] != '0' else '1')
    r = _mutate(lambda d: d['derived_artifacts'].__setitem__(
        'panel_enriched.pkl', typo))
    check('a one-character transcription error is caught',
          r['label'] == I.DIFFERENT)
    short = real[:8]
    r = _mutate(lambda d: d['derived_artifacts'].__setitem__(
        'panel_enriched.pkl', short))
    check('a truncated "short hash" is not accepted as a match',
          r['label'] == I.DIFFERENT)
    check('the spec itself is loaded from the artifact, never typed',
          I.load_spec()[1] == SPEC_SHA)


def test_the_gate_cannot_be_operated_blind():
    print('\nI. the gate refuses to run on nothing')
    with tempfile.TemporaryDirectory() as td:
        for name, write in (('absent.json', None), ('empty.json', b''),
                            ('bad.json', b'{not json'),
                            ('partial.json', b'{"leaf_inputs": {}}')):
            p = os.path.join(td, name)
            if write is not None:
                open(p, 'wb').write(write)
            try:
                I.load_spec(p)
                check(f'{name} raises', False, 'no raise')
            except I.IdentityError as exc:
                check(f'{name} raises a NAMED error', str(exc).split(':')[0] in
                      ('SPEC_ABSENT', 'SPEC_EMPTY', 'SPEC_UNPARSEABLE',
                       'SPEC_INCOMPLETE'), str(exc)[:60])
    r = I.verify(['not', 'a', 'mapping'])
    check('a non-descriptor is REFUSED', r['label'] == I.REFUSED)
    try:
        I.describe_files({'nope': os.path.join(HERE, 'does_not_exist.bin')})
        check('describe_files refuses an absent input', False, 'no raise')
    except I.IdentityError as exc:
        check('describe_files refuses an absent input',
              'INPUT_ABSENT' in str(exc))


def test_guard_deletion():
    print('\nJ/K. delete the guards and the refusals go away')
    # GD-1: the completeness guard. This is a PRECISION guard, not a safety
    # guard, and the proof says so rather than dressing it up: with it deleted
    # an incomplete descriptor is still not confirmed, it is merely relabelled
    # DIFFERENT instead of REFUSED. What is lost is the distinction between
    # "this run declared something else" and "this run did not say", which are
    # different conversations with whoever ran it.
    orig = I.REQUIRED_GROUPS
    try:
        I.REQUIRED_GROUPS = ()
        d = good_descriptor()
        d.pop('solver'); d.pop('seed_protocol')
        r = I.verify(d)
        check('GD-1 with REQUIRED_GROUPS emptied, an incomplete descriptor is '
              'no longer REFUSED', r['label'] != I.REFUSED, r['label'])
        check('  it is relabelled DIFFERENT rather than confirmed -- the guard '
              'buys precision, not safety, and is reported as such',
              r['label'] == I.DIFFERENT, r['label'])
        check('  and the gate does not crash on the undeclared groups',
              r['n_mismatches'] > 0)
    finally:
        I.REQUIRED_GROUPS = orig
    d = good_descriptor(); d.pop('solver'); d.pop('seed_protocol')
    check('  with the guard restored it is refused again',
          I.verify(d)['label'] == I.REFUSED)

    # GD-2: the forbidden-season guard.
    orig_f = I.FORBIDDEN_SEASONS
    try:
        I.FORBIDDEN_SEASONS = ()
        d = good_descriptor()
        d['consumed_seasons'] = [2024, 2025, 2026]
        r = I.verify(d)
        check('GD-2 with FORBIDDEN_SEASONS emptied, a 2026-consuming run is '
              f'labelled {I.CONFIRMED!r}', r['label'] == I.CONFIRMED, r['label'])
    finally:
        I.FORBIDDEN_SEASONS = orig_f
    d = good_descriptor(); d['consumed_seasons'] = [2024, 2025, 2026]
    check('  and with the guard restored it is refused again',
          I.verify(d)['label'] == I.REFUSED)

    # GD-3: the mismatch collector. Without it every altered run is "frozen".
    orig_c = I._cmp_map
    try:
        I._cmp_map = lambda *a, **k: []
        d = good_descriptor()
        d['derived_artifacts']['panel_enriched.pkl'] = '0' * 64
        d['seed_protocol']['base_seed'] = 1
        r = I.verify(d)
        check('GD-3 with the comparator stubbed empty, an altered generation '
              'claims the frozen label', r['label'] == I.CONFIRMED, r['label'])
    finally:
        I._cmp_map = orig_c
    d = good_descriptor()
    d['derived_artifacts']['panel_enriched.pkl'] = '0' * 64
    check('  and with the comparator restored it is relabelled',
          I.verify(d)['label'] == I.DIFFERENT)


if __name__ == '__main__':
    for t in (test_the_matching_case, test_stale_and_wrong_artifacts,
              test_row_ordering_and_dtype, test_seed_draw_and_solver,
              test_upstream_identity_and_features, test_silence_is_not_agreement,
              test_forbidden_2026, test_a_typed_hash_is_still_checked,
              test_the_gate_cannot_be_operated_blind, test_guard_deletion):
        t()
    print(f'\n{P} passed, {F} failed')
    sys.exit(1 if F else 0)
