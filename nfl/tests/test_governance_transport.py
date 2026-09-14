"""WS-D: the pipeline must carry what the producing layer said about itself.

THE DEFECT THIS MODULE EXISTS TO KEEP REPAIRED

`nfl/production/nonqb/layers.py` emits structured governance the moment it
runs: `participation` raises `known limitation: pass-snap participation is an
upper bound on routes run`, `receiving_conversion` returns
`governance='HOLD_CHARACTERIZED + CALIBRATION_DEFECT'` alongside two warnings
naming SIGNAL_WEAK and CALIBRATION_DEFECT, and both TD layers return
`governance='HOLD_TENTATIVE'`.

None of it reached the artifact. `_nonqb_stage` aggregated those layers and
returned an Outcome with no `warnings` and no `governance` key, and
`StageResult` copied `evidence['warnings']` and a metrics whitelist and nothing
else. A sealed run therefore recorded `"warnings": []` on participation,
targets_carries, conversion and td_layer, and the only surviving copy of those
governance states was a sentence a human had retyped into the caller's
`spec_version` literal -- where the two copies had already drifted:
`layers.SPEC['appearance']` says `governance INFORMATION_CONSTRAINED` and the
call site passed `'P3 appearance'`.

WHAT IS AND IS NOT TESTED HERE

This is TRANSPORT. Every check below asks whether a fact the layer stated
arrives unchanged, with the name of the layer that stated it. Not one of them
asks whether a warning should block publication, rank above another, or change
a gate -- that is a governance question, it is owned elsewhere, and a test in
this file asserting it would be this module deciding it.

The two directions are checked separately and both matter:
  NOTHING LOST      every warning and governance value a layer emitted is
                    present in the stage result and in run_status.json.
  NOTHING INVENTED  the stage result contains no warning, governance value or
                    severity that no layer emitted.
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _q in (_ROOT,):
    if _q not in sys.path:
        sys.path.insert(0, _q)

from sportsplatform.governance.outcome import Outcome, State      # noqa: E402
from nfl.identity import code_identity as CI                      # noqa: E402
from nfl.prospective import artifact as ART                       # noqa: E402
from nfl.product import confidence as CONF                        # noqa: E402
from nfl.production import draw_coherence as DC                   # noqa: E402
from nfl.production import pipeline as PL                         # noqa: E402
from nfl.production import run_forecast as RUN                    # noqa: E402
from nfl.production.nonqb import layers as LY                     # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


# The layer outcomes below are built from `layers.SPEC` and
# `layers.KNOWN_LIMITATIONS` themselves, never from a copy of their text. A
# fixture that retyped the strings would pass while the real ones drifted --
# which is the defect, reproduced inside its own test.
def _participation_like():
    return Outcome.ok(
        'PARTICIPATION_OK', value={'p1': 1},
        spec_version=LY.SPEC['participation'], test_only=True,
        warnings=['known limitation: pass-snap participation is an upper '
                  'bound on routes run'], n_players=1)


def _conversion_like():
    return Outcome.ok(
        'CONVERSION_OK', value={'receptions': 1},
        spec_version=LY.SPEC['receiving_conversion'], test_only=True,
        governance='HOLD_CHARACTERIZED + CALIBRATION_DEFECT',
        warnings=['known limitation: RC1 SIGNAL_WEAK',
                  'governance: receiving_baseline_calibration '
                  'CALIBRATION_DEFECT'])


def _td_like(code='TD_LAYER_OK', spec_key='td_layer'):
    return Outcome.ok(
        code, value={'td': 1}, spec_version=LY.SPEC[spec_key],
        governance='HOLD_TENTATIVE', baseline='B_pos',
        warnings=['known limitation: TD2 pooled positional control, '
                  'HOLD_TENTATIVE'])


def _appearance_like():
    return Outcome.ok('APPEARANCE_OK', value={'p1': 1},
                      spec_version=LY.SPEC['appearance'], n_players=1)


# ---------------------------------------------------------------- producers
def test_the_producing_layer_still_emits_what_this_transport_carries():
    """If layers.py ever stops declaring these, this file is measuring air.

    layers.py is hashed by the Q9 frozen candidate identity and no workstream
    may edit it, so this is a guard against the transport outliving its
    source, not a request for a change.
    """
    src = open(os.path.join(_ROOT, 'nfl', 'production', 'nonqb',
                            'layers.py')).read()
    check('participation declares its upper-bound limitation',
          'upper bound on routes run' in src)
    check('conversion declares CALIBRATION_DEFECT as a governance value',
          "governance='HOLD_CHARACTERIZED + CALIBRATION_DEFECT'" in src)
    check('conversion declares SIGNAL_WEAK as a warning',
          'known limitation: RC1 SIGNAL_WEAK' in src)
    check('both TD layers declare HOLD_TENTATIVE',
          src.count("governance='HOLD_TENTATIVE'") == 2,
          str(src.count("governance='HOLD_TENTATIVE'")))
    check('appearance declares INFORMATION_CONSTRAINED in its SPEC',
          'INFORMATION_CONSTRAINED' in LY.SPEC['appearance'],
          LY.SPEC['appearance'])


# ------------------------------------------------------------- aggregation
def test_aggregation_keeps_every_warning_and_names_its_layer():
    got = [('receiving_td', _td_like('TD_LAYER_OK', 'td_layer')),
           ('rushing_td', _td_like('RUSHING_TD_OK', 'rushing_td'))]
    f = RUN._governance_facts(got)
    check('two layers raising the same sentence stay two facts',
          len(f['warnings']) == 2 and len(f['warnings_detail']) == 2,
          str(f['warnings']))
    check('each warning names the layer that raised it',
          {r['layer'] for r in f['warnings_detail']} ==
          {'receiving_td', 'rushing_td'},
          str(f['warnings_detail']))
    check('the warning text is the layer text, unedited',
          all(r['warning'] ==
              'known limitation: TD2 pooled positional control, HOLD_TENTATIVE'
              for r in f['warnings_detail']),
          str(f['warnings_detail']))
    check('both governance values survive, one per layer',
          [r['governance'] for r in f['governance']] ==
          ['HOLD_TENTATIVE', 'HOLD_TENTATIVE'], str(f['governance']))


def test_aggregation_invents_nothing():
    """A layer that declared no governance and no severity gets neither."""
    f = RUN._governance_facts([('appearance', _appearance_like())])
    check('no warning is manufactured for a silent layer',
          f['warnings'] == [] and f['warnings_detail'] == [], str(f))
    check('no governance value is manufactured',
          f['governance'] == [], str(f['governance']))
    f2 = RUN._governance_facts([('participation', _participation_like())])
    check('no severity is invented where the layer declared none',
          all('severity' not in r for r in f2['warnings_detail']),
          str(f2['warnings_detail']))


def test_a_declared_severity_is_carried_and_not_reranked():
    o = Outcome.ok('X_OK', value=1, warnings=['w'], governance='G',
                   severity='ADVISORY')
    f = RUN._governance_facts([('x', o)])
    check('a declared severity reaches the warning record',
          f['warnings_detail'][0].get('severity') == 'ADVISORY',
          str(f['warnings_detail']))
    check('a declared severity reaches the governance record',
          f['governance'][0].get('severity') == 'ADVISORY',
          str(f['governance']))


def test_the_composed_spec_version_is_derived_not_retyped():
    f = RUN._governance_facts([('appearance', _appearance_like())])
    check('a single-layer stage reports the layer spec verbatim',
          f['spec_version'] == LY.SPEC['appearance'], f.get('spec_version'))
    check("appearance's governance state is IN the reported spec version",
          'INFORMATION_CONSTRAINED' in f['spec_version'],
          f.get('spec_version'))
    check("the retyped literal 'P3 appearance' is not what is reported",
          f['spec_version'] != 'P3 appearance', f.get('spec_version'))
    g = RUN._governance_facts([('receiving_td', _td_like()),
                               ('rushing_td', _td_like('RUSHING_TD_OK',
                                                       'rushing_td'))])
    check('a multi-layer stage names each layer beside its spec',
          g['spec_version'].startswith('receiving_td=')
          and 'rushing_td=' in g['spec_version'], g.get('spec_version'))
    n = RUN._governance_facts([('x', Outcome.ok('X_OK', value=1))])
    check('a stage whose layers published no spec reports none, not a blank',
          'spec_version' not in n, str(n))


# ------------------------------------------------------------- StageResult
def _stage(out, spec_version='CALLER LITERAL', stage='conversion'):
    p = PL.Pipeline(run_id='t', out_dir=pathlib.Path(tempfile.mkdtemp()),
                    arm='A', written_at='2026-09-14T00:00:00Z')
    return p, p.run_stage(stage, lambda: out, spec_version=spec_version)


def test_stage_result_carries_governance_out_of_the_evidence():
    got = [('receiving_conversion', _conversion_like())]
    out = Outcome.ok('CONVERSION_OK', value={}, layers={}, spec_versions={
        'receiving_conversion': LY.SPEC['receiving_conversion']},
        **RUN._governance_facts(got))
    _p, r = _stage(out)
    check('warnings are no longer empty on the conversion stage',
          len(r.warnings) == 2, str(r.warnings))
    check('CALIBRATION_DEFECT arrives by name',
          any('CALIBRATION_DEFECT' in w for w in r.warnings), str(r.warnings))
    check('SIGNAL_WEAK arrives by name',
          any('SIGNAL_WEAK' in w for w in r.warnings), str(r.warnings))
    check('the governance value arrives as a record, not as prose',
          r.governance == [{'layer': 'receiving_conversion',
                            'governance': 'HOLD_CHARACTERIZED + '
                                          'CALIBRATION_DEFECT'}],
          str(r.governance))
    check('the per-layer spec version survives',
          r.spec_versions == {'receiving_conversion':
                              LY.SPEC['receiving_conversion']},
          str(r.spec_versions))


def test_a_bare_governance_value_is_not_given_an_invented_layer_name():
    """A single layer reporting `governance='...'` has no layer name here."""
    _p, r = _stage(_conversion_like())
    check('one record is produced', len(r.governance) == 1, str(r.governance))
    check('the layer is recorded as unknown rather than guessed',
          r.governance[0]['layer'] is None, str(r.governance))
    check('the value itself is unchanged',
          r.governance[0]['governance'] ==
          'HOLD_CHARACTERIZED + CALIBRATION_DEFECT', str(r.governance))


def test_the_stage_answers_for_its_own_spec_version():
    """The drift: a caller literal must not outrank what the layer published."""
    _p, r = _stage(_appearance_like(), spec_version='P3 appearance',
                   stage='appearance')
    check('the layer spec wins over the retyped literal',
          r.spec_version == LY.SPEC['appearance'], r.spec_version)
    check('INFORMATION_CONSTRAINED reaches the stage result',
          'INFORMATION_CONSTRAINED' in (r.spec_version or ''), r.spec_version)
    _p2, r2 = _stage(Outcome.ok('FEATURES_OK', value={}),
                     spec_version='prior-only, ordinal prefix cut',
                     stage='feature_build')
    check('a stage that published no spec keeps the caller label',
          r2.spec_version == 'prior-only, ordinal prefix cut', r2.spec_version)


def test_nothing_is_lost_between_stage_result_and_run_status_json():
    got = [('participation', _participation_like())]
    out = Outcome.ok('PARTICIPATION_OK', value={}, **RUN._governance_facts(got))
    p, r = _stage(out, stage='participation')
    p.persist()
    d = json.loads((p.out_dir / 'run_status.json').read_text())
    s = [x for x in d['stages'] if x['stage'] == 'participation'][0]
    check('the persisted stage carries the warning',
          s['warnings'] == r.warnings and len(s['warnings']) == 1,
          str(s['warnings']))
    check('the persisted stage carries the structured record',
          s['warnings_detail'] == [{'layer': 'participation',
                                    'warning': r.warnings[0].split(': ', 1)[1]}],
          str(s.get('warnings_detail')))
    check('the persisted spec version is the layer constant',
          s['spec_version'] == LY.SPEC['participation'], s.get('spec_version'))
    check('as_dict() exposes every transported field',
          {'governance', 'spec_versions', 'warnings_detail'} <= set(s),
          str(sorted(s)))


def test_a_blocked_stage_still_reports_what_it_managed_to_say():
    o = Outcome.blocked('BLOCKED_UPSTREAM_APPEARANCE', 'upstream is DEFERRED',
                        cause=__import__(
                            'sportsplatform.governance.outcome',
                            fromlist=['Cause']).Cause.DEPENDENCY,
                        warnings=['known limitation: still true while blocked'],
                        governance='HOLD_TENTATIVE')
    _p, r = _stage(o, stage='conversion')
    check('a BLOCKED stage keeps its warnings',
          r.warnings == ['known limitation: still true while blocked'],
          str(r.warnings))
    check('a BLOCKED stage keeps its governance value',
          r.governance and r.governance[0]['governance'] == 'HOLD_TENTATIVE',
          str(r.governance))


# --------------------------------------------------------- the QB two paths
def test_both_qb_paths_declare_the_same_known_limitations():
    """§2.4: the candidate path carried none while running QB V1 anyway."""
    src = open(os.path.join(_ROOT, 'nfl', 'production',
                            'run_forecast.py')).read()
    n = src.count("warnings=[f'known limitation: {k}'\n"
                  "                      for k in QBV1.KNOWN_LIMITATIONS]")
    m = src.count("warnings=[f'known limitation: {k}'\n"
                  "                              for k in "
                  "QBV1.KNOWN_LIMITATIONS]")
    check('both QB returns declare QB V1 limitations', n + m == 2,
          f'candidate={n} baseline={m}')
    check('the limitation list is read from the layer, not retyped',
          "QBV1.KNOWN_LIMITATIONS" in src and
          'multi_qb_over_prediction' not in src)


def test_the_stage_layer_map_still_covers_every_transported_layer():
    """A layer key added to the transport must also be a reported layer.

    `_assert_every_layer_is_reported` raises ENGINE_LAYER_NOT_REPORTED for an
    engine layer no stage answers for. The transport names layers in its
    records, so a name here that no stage maps would be a governance fact
    attributed to a layer the artifact never reports.
    """
    src = open(os.path.join(_ROOT, 'nfl', 'production',
                            'run_forecast.py')).read()
    check('the reporting guard is still present and still raises',
          'ENGINE_LAYER_NOT_REPORTED' in src)
    check('the transport adds no layer key of its own',
          "_governance_facts" in src and
          src.count("STAGE_LAYERS = {") == 1)


# ===========================================================================
# (d) CODE IDENTITY -- adopted, not reinvented
# ===========================================================================
def test_the_run_identity_does_not_key_on_a_count():
    cv = RUN.code_commit()
    check('code_commit no longer emits the count-keyed form',
          not CI.refuses_count_keyed(cv), cv)
    check('it emits the one declared format, clean or dirty',
          '+src1[' in cv and len(cv.split('+src1[')[0]) == 40, cv)
    # The word survives in the docstring that records the defect. What must
    # not survive is the MECHANISM: no local git call, no local counting.
    src = open(os.path.join(_ROOT, 'nfl', 'production',
                            'run_forecast.py')).read()
    check('the identity module is the source, not a local reimplementation',
          'subprocess' not in src and "'--porcelain'" not in src)


def test_a_run_cannot_move_its_own_identity_by_writing_its_outputs():
    """dF/dD = 0. The count-keyed form failed this; measured, not argued."""
    before = RUN.code_commit()
    d = pathlib.Path(_ROOT) / 'nfl' / 'research' / 'live' / '__transport_probe__'
    try:
        d.mkdir(parents=True, exist_ok=True)
        (d / 'run_status.json').write_text('{}')
        during = RUN.code_commit()
        (d / 'player_draws.npz').write_bytes(b'\x00')
        during2 = RUN.code_commit()
    finally:
        shutil.rmtree(d, ignore_errors=True)
    after = RUN.code_commit()
    check('writing a run output does not change the code version',
          before == during == during2 == after,
          f'{before} / {during} / {during2} / {after}')


def test_every_generated_subtree_is_outside_identity_b():
    o = CI.code_identity()
    if o.state is not State.PASS:
        check('code identity resolved', False, f'{o.code}: {o.detail[:120]}')
        return
    dirty = [e['path'] for e in o.value['dirty_source_files']]
    bad = [p for p in dirty
           if any(p.startswith(g) for g in CI.GENERATED_SUBTREES)]
    check('no generated subtree contributes to the source digest',
          not bad, str(bad))
    check('the scope declaration is itself inside the digest',
          'scope' in o.value and o.value['scope']['source_roots'])


# ===========================================================================
# (c) P2 -- draw coherence on the published matrices
# ===========================================================================
def test_the_coherence_call_site_is_at_p2_and_not_in_the_engine():
    src = open(os.path.join(_ROOT, 'nfl', 'production',
                            'run_forecast.py')).read()
    check('assert_draw_coherence is called from run_forecast',
          'DC.assert_draw_coherence(' in src)
    body = src.split('def _draws(')[1].split('\n    def ')[0] \
        if 'def _draws(' in src else ''
    check('the call is inside _draws(), where the sealed matrices exist',
          'DC.assert_draw_coherence(' in body)
    check('the caller declares it holds the published team carry vector',
          "include_carries='team_volume/team_carries' in _p2" in src)
    check('shared_pass_live is read from the component list, not inferred',
          "shared_pass_live='C3' in (fx.get('_candidate_applied')" in src)


def test_absent_layers_file_not_applicable_rather_than_pass_or_silence():
    """68 of 101 sealed runs carry no receiving or rushing layer."""
    import numpy as np
    qb_only = {f'qb/{k}': np.zeros((2, 4)) for k in
               ('att', 'cmp', 'ptd', 'pyds', 'int', 'db', 'sacks', 'scr',
                'rush_opp', 'ryds', 'rush_td')}
    o = DC.assert_draw_coherence(qb_only, team_rows={}, shared_pass_live=False,
                                 include_carries=False)
    comp = o.evidence.get('components') or {}
    check('a QB-only run does not refuse',
          o.state in (State.PASS, State.NOT_APPLICABLE, State.DEFERRED),
          f'{o.state.value}[{o.code}]')
    check('receiving files NOT_APPLICABLE, not PASS',
          comp.get('receiving', {}).get('state') == 'NOT_APPLICABLE',
          str(comp.get('receiving')))
    check('rushing files NOT_APPLICABLE, not PASS',
          comp.get('rushing', {}).get('state') == 'NOT_APPLICABLE',
          str(comp.get('rushing')))


def test_the_verdict_is_never_silent_even_before_registration():
    src = open(os.path.join(_ROOT, 'nfl', 'production',
                            'run_forecast.py')).read()
    check("summary carries draw_coherence unconditionally",
          "summary['draw_coherence'] = (" in src)
    check('it records whether the key is a registered invariant yet',
          "'registered_as_invariant':" in src)
    check('filing into _inv is gated on the registration, with the reason',
          "'draw_coherence' in ART.INVARIANTS" in src)
    check('artifact.py still declares the pending hand-off',
          'draw_coherence' in ART.PENDING_INVARIANT_REGISTRATION
          or 'draw_coherence' in ART.INVARIANTS)


def test_the_carry_checks_stay_diagnostic_and_stay_out_of_the_engine():
    for k in DC.NOT_ENGINE_EVALUABLE:
        check(f'{k} is DIAGNOSTIC',
              DC.COHERENCE[k]['class'] == DC.DIAGNOSTIC,
              DC.COHERENCE[k]['class'])
    check('every not-engine-evaluable check reads team_volume',
          all('team_volume' in DC.COHERENCE[k]['layers']
              for k in DC.NOT_ENGINE_EVALUABLE))


# ===========================================================================
# (b) WS-M -- the confidence inputs that exist before the seal
# ===========================================================================
def test_readiness_is_resolved_before_the_forecast_not_after_the_outcome():
    src = open(os.path.join(_ROOT, 'nfl', 'tools', 'make_board.py')).read()
    i_ready = src.find("fx['readiness'] = ready")
    i_build = src.find('summary = RUN.build(args, fx)')
    check('readiness is computed and handed to the run before it builds',
          0 < i_ready < i_build, f'{i_ready} vs {i_build}')
    check('the board scores against the SAME object that was sealed',
          src.count('ready = {t: RD.team_readiness(') == 1)
    rsrc = open(os.path.join(_ROOT, 'nfl', 'production',
                             'run_forecast.py')).read()
    check('the run seals readiness into its own status record',
          "summary['readiness'] = fx.get('readiness')" in rsrc)
    check('the scoring rule in force is pinned alongside it',
          "summary['confidence_contract'] = fx.get('confidence_contract')"
          in rsrc)


def test_the_confidence_contract_is_read_from_the_module_not_retyped():
    src = open(os.path.join(_ROOT, 'nfl', 'tools', 'make_board.py')).read()
    check('dimensions come from confidence.DIMENSIONS',
          'list(CONF.DIMENSIONS)' in src)
    check('weights come from confidence.WEIGHTS',
          'dict(CONF.WEIGHTS)' in src)
    check('the flat-weight note travels with them',
          'CONF.WEIGHTS_NOTE' in src)
    check('status_certainty is the dimension readiness feeds',
          'status_certainty' in CONF.DIMENSIONS)


def test_nothing_historical_is_backfilled():
    """A run sealed before this change must stay silent, not look populated."""
    p = os.path.join(_ROOT, 'nfl', 'research', 'shadow', 'g1_ne_sea',
                     'run_status.json')
    if not os.path.exists(p):
        check('the only graded run is present to check', False, p)
        return
    d = json.loads(open(p).read())
    check('the graded run still carries no readiness key',
          'readiness' not in d, str(sorted(d)[:6]))
    check('and no confidence contract',
          'confidence_contract' not in d)
    src = open(os.path.join(_ROOT, 'nfl', 'production',
                            'run_forecast.py')).read()
    check('the run records absence as absence, never as a default',
          "summary['readiness'] = fx.get('readiness')" in src
          and "summary['readiness'] = fx.get('readiness', {})" not in src)


def test_no_sealed_confidence_input_reads_generated_artifact_state():
    """The rule WS-E paid for: D may not enter the sealed body, hashed or not."""
    src = open(os.path.join(_ROOT, 'nfl', 'tools', 'make_board.py')).read()
    head = src.split('summary = RUN.build(args, fx)')[0]
    check('readiness is built from captures and the clock, not from run_dir',
          'run_dir' not in head.split("fx['readiness']")[0][-2000:])
    check('the contract is a declaration, not a measurement of this run',
          'run_id' not in src.split("fx['confidence_contract'] = {")[1]
          .split('}')[0])
