"""The ownership audit must be able to FIND a bypass, or its clean result is
worth nothing.

Every family came back NOT_IMPLEMENTED. That is either the truth about this
repository or a scanner that cannot see, and the difference is what this module
establishes -- by feeding the SAME scanner code that really does apply an
adjustment and requiring it to fire.

THREE FAILURES THE CONTROLS ALREADY CAUGHT, each of which would have shipped a
confident and wrong sentence:

  1. EXACT-TOKEN MATCHING. `pace_factor` is not the string `pace`, so a module
     multiplying volume by `pace_factor` produced no hit and all nine families
     read NOT_IMPLEMENTED. That was a fact about the matcher being reported as
     a fact about the repository.
  2. SCANNING `nfl/production` ALONE. It imports nfl.product, nfl.capture,
     nfl.prospective, nfl.identity and nfl.accounting; an effect applied in any
     of those was invisible.
  3. COUNTING A HIT AS AN APPLICATION. The widened scan returned eight
     REGISTERED_BUT_BYPASSED families, none of which applied anything: the hits
     were a captured source's column header, a quarantine list naming the
     fields it REFUSES, and English prose inside string constants.
"""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production import ownership_audit as OA                   # noqa: E402
from nfl.production import adjustment_registry as AR               # noqa: E402
from sportsplatform.governance.outcome import State                # noqa: E402

PASSED = 0
FAILED = 0
NOT_EXECUTED = []


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


BYPASS = '''
"""A layer that scales team volume by tempo. This docstring mentions roof and
surface and pressure, and none of those may produce a hit."""
# A comment naming defenders_in_box and defense_coverage_type. Also inert.


def adjust(team_rows, pace_factor):
    for r in team_rows:
        r['team_off_snaps'] = r['team_off_snaps'] * pace_factor
    return team_rows
'''

GOVERNED = '''
from nfl.production import adjustment_registry


def adjust(team_rows, pace_factor, frame_tags):
    v = adjustment_registry.assert_may_apply(
        'pace_v1', calling_layer='team_volume', frame_tags=frame_tags)
    if v.state.name != 'PASS':
        return v
    for r in team_rows:
        r['team_off_snaps'] = r['team_off_snaps'] * pace_factor
    return team_rows
'''


def test_A_the_scanner_fires_on_a_real_bypass():
    print('\nA. CONTROL: a genuine unrouted application is detected')
    s = OA.scan_source(BYPASS, 'bypass.py')
    fields = OA.FAMILIES['pace_v1']['fields']
    hit = OA.match_fields(fields, s['tokens'])
    check('the pace identifier is seen', bool(hit), str(hit))
    check('  matched through its COMPONENTS, not exact equality',
          'pace' in hit and 'pace_factor' in hit.get('pace', []), str(hit))
    arith = OA.match_fields(fields, s['binop_operands'])
    check('  and seen as a DIRECT ARITHMETIC operand, the shape a bypass takes',
          bool(arith), str(arith))
    check('  the module does NOT call the registry', not s['calls_registry'])
    check('  and propagates no lineage', not s['propagates_lineage'])


def test_B_the_governed_version_reads_as_governed():
    print('\nB. the same application, routed, reads as routed')
    s = OA.scan_source(GOVERNED, 'governed.py')
    check('the pace identifier is still seen',
          bool(OA.match_fields(OA.FAMILIES['pace_v1']['fields'], s['tokens'])))
    check('  and now the module DOES call the registry', s['calls_registry'])
    check('  and carries lineage', s['propagates_lineage'])


def test_C_the_matcher_does_not_match_substrings():
    print('\nC. `pace` is inside `namespace` thirty times in this tree')
    check("'namespace' does NOT match the field 'pace'",
          not OA.field_matches('pace', 'namespace'))
    check("'pace_factor' DOES", OA.field_matches('pace', 'pace_factor'))
    check("'neutralPace' does too, through camelCase",
          OA.field_matches('pace', 'neutralPace'))
    check("'PARTIAL_PLAYER_COVERAGE' does not match "
          "'defense_coverage_type'",
          not OA.field_matches('defense_coverage_type',
                               'PARTIAL_PLAYER_COVERAGE'))
    check("'wind_speed' matches 'wind'", OA.field_matches('wind', 'wind_speed'))
    check("'window' does not", not OA.field_matches('wind', 'window'))


def test_D_prose_and_comments_cannot_produce_a_hit():
    print('\nD. prose is not football')
    s = OA.scan_source(BYPASS, 'bypass.py')
    for tok in ('roof', 'surface', 'pressure', 'defenders_in_box',
                'defense_coverage_type'):
        check(f'  {tok!r}, only in a comment or docstring, is not a hit',
              tok not in s['tokens'], tok)
    live = OA.scan_source("x = {'roof': 1}\ny = x['roof']\n", 'live.py')
    check("  but 'roof' in actual code IS a hit", 'roof' in live['tokens'])


def test_E_site_classification():
    print('\nE. a hit is classified before it is counted')
    cases = [
        ('nfl/product/x.py', {'surface': ['this exists to surface the item']},
         OA.PROSE, 'an English sentence'),
        ('nfl/capture/x.py',
         {'was_pressure': ['play_id,was_pressure,route,defense_coverage_type']},
         OA.SCHEMA_LIST, 'a comma-joined column header'),
        ('nfl/ingest/allowlist.py', {'temp': ['temp']},
         OA.ACQUISITION_OR_GUARD, 'a quarantine list'),
        ('nfl/production/x.py', {'roof': ['roof']},
         OA.APPLICATION_CANDIDATE, 'a bare field name in a forecast layer'),
    ]
    for path, hits, want, why in cases:
        got = OA._classify(path, hits)
        check(f'  {why} -> {want}', got == want, got)


def test_F_an_unreviewed_candidate_site_REFUSES():
    print('\nF. a site nobody has opened is not a clean site')
    saved = dict(OA.DISPOSITIONS)
    try:
        OA.DISPOSITIONS.clear()
        o = OA.audit()
        check('with no dispositions recorded, the audit FAILS',
              o.state is State.FAIL
              and o.code == 'OWNERSHIP_AUDIT_UNREVIEWED_SITE',
              f'{o.state}[{o.code}]')
        check('  naming the site', bool(o.evidence.get('unreviewed')),
              str(o.evidence.get('unreviewed'))[:120])
    finally:
        OA.DISPOSITIONS.clear()
        OA.DISPOSITIONS.update(saved)
    o = OA.audit()
    check('  and passes again once the disposition is restored',
          o.state is State.PASS, f'{o.state}[{o.code}]')


def test_G_the_audit_over_the_real_tree():
    print('\nG. the audit itself')
    o = OA.audit()
    check('the audit completes', o.state is State.PASS, f'{o.state}[{o.code}]')
    n = o.evidence['n_files_scanned']
    check(f'  it scanned the whole production path ({n} modules)', n >= 120,
          str(n))
    check('  research, tests and tools are excluded by declaration',
          set(o.evidence['scan_excluded'])
          == {'nfl/research', 'nfl/tests', 'nfl/tools'},
          str(o.evidence['scan_excluded']))
    check('  every registered adjustment is covered by a family',
          not o.evidence['adjustments_not_covered_by_this_audit'],
          str(o.evidence['adjustments_not_covered_by_this_audit']))
    for aid in AR.ADJUSTMENTS:
        check(f'  {aid} has a verdict',
              o.value.get(aid, {}).get('audit_state') in (
                  OA.REGISTERED_AND_ENFORCED, OA.REGISTERED_BUT_BYPASSED,
                  OA.NOT_REGISTERED, OA.NOT_IMPLEMENTED),
              str(o.value.get(aid, {}).get('audit_state')))


def test_H_ownership_is_not_asserted():
    print('\nH. SINGLE_ADJUSTMENT_OWNERSHIP stays NO')
    o = OA.audit()
    check('the audit does NOT verify single ownership',
          o.evidence['single_adjustment_ownership_verified'] is False)
    check('  because no module on the production path calls the registry',
          o.evidence['registry_callers_in_production'] == [],
          str(o.evidence['registry_callers_in_production']))
    check('  and nothing is applying an adjustment to verify',
          o.evidence['n_implemented_in_production'] == 0)
    check('  the audit records that it can only disprove, never prove',
          'never proves it' in o.evidence['audit_can_only_disprove'])


def test_I_a_null_scanner_would_be_caught():
    print('\nI. the null-scanner check')
    s = OA.scan_source(BYPASS, 'bypass.py')
    check('the scanner returns a populated token set',
          len(s['tokens']) >= 4, str(len(s['tokens'])))
    check('  including identifiers in no family',
          'team_rows' in s['tokens'] and 'team_off_snaps' in s['tokens'],
          str(sorted(s['tokens'])))
    # A DEF NAME IS NOT A Name NODE. `apply_pace_adjustment` -- the most
    # obvious bypass there is -- was invisible until the scanner collected
    # function and class names explicitly.
    d = OA.scan_source('def apply_pace_adjustment(x):\n    return x\n', 'd.py')
    check('  and a function NAME is collected, so a bypass cannot hide in one',
          bool(OA.match_fields(OA.FAMILIES['pace_v1']['fields'], d['tokens'])),
          str(sorted(d['tokens'])))


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in (test_A_the_scanner_fires_on_a_real_bypass,
               test_B_the_governed_version_reads_as_governed,
               test_C_the_matcher_does_not_match_substrings,
               test_D_prose_and_comments_cannot_produce_a_hit,
               test_E_site_classification,
               test_F_an_unreviewed_candidate_site_REFUSES,
               test_G_the_audit_over_the_real_tree,
               test_H_ownership_is_not_asserted,
               test_I_a_null_scanner_would_be_caught):
        fn()
    for n in NOT_EXECUTED:
        print(f'  NOT_EXECUTED {n}')
    print(f'\n{PASSED} passed, {FAILED} failed, {len(NOT_EXECUTED)} NOT_EXECUTED')
    raise SystemExit(1 if FAILED else 0)
