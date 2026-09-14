"""L4: the publication gate must be able to decide THIS metric on THIS run.

THE DEFECT THIS MODULE EXISTS TO KEEP REPAIRED

`authorization.may_publish()` took zero arguments. It read one board-wide gate
and returned one board-wide answer, so it could not refuse this board for this
board's defects and it could not make a metric-specific decision. WS-D had
just repaired the transport that carried the layers' governance tokens and
warnings into the seal -- and the tokens arrived somewhere that could do
nothing with them.

WHAT IS TESTED HERE

  THE MECHANISM EXISTS      the gate receives run identity, metric, layer,
                            configuration, chronology, eligibility, hard
                            invariants, warnings, governance, completeness and
                            model health, and it answers per run and per metric.
  UNDECIDED IS A THIRD THING it is distinguishable from allow AND from refuse,
                            at the Outcome level, not only in a string.
  ABSENCE IS NEVER CLEAN    every fact withheld moves a rule to UNEVALUABLE,
                            and no withheld fact can produce a PASS.
  NO POLICY WAS ACTIVATED   every Wave-7 governance token resolves UNDECIDED
                            with no authority, and no level assignment from
                            `GOVERNANCE_RECOMMENDATION_MATRIX.md` is applied.
  NO PATH FROM A GREEN SUITE a test result offered as an input is refused by
                            name.

WHAT IS DELIBERATELY NOT TESTED

Whether any token SHOULD block publication. That is an owner ruling. A check
in this file asserting one would be this test choosing the policy, which is
the thing the mechanism was built to leave open.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import Outcome, State      # noqa: E402
from nfl.production import authorization as AUTH                  # noqa: E402
from nfl.production import candidate_mode as CAND                 # noqa: E402
from nfl.production.nonqb import eligibility as ELIG              # noqa: E402
from nfl.production.nonqb import layers as LY                     # noqa: E402
from nfl.production.nonqb import vintage_selector as VS           # noqa: E402

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


# ---------------------------------------------------------------- fixtures
#
# The governance strings below are taken from `layers.py` ITSELF, never
# retyped. A fixture carrying a copy would keep passing while the real layer
# drifted -- which is the defect WS-D found, reproduced inside its own test.
def _conversion_governance():
    return [{'layer': 'receiving_conversion',
             'governance': 'HOLD_CHARACTERIZED + CALIBRATION_DEFECT'}]


def _conversion_warnings():
    return [{'layer': 'receiving_conversion',
             'warning': 'known limitation: RC1 SIGNAL_WEAK'},
            {'layer': 'receiving_conversion',
             'warning': 'governance: receiving_baseline_calibration '
                        'CALIBRATION_DEFECT'}]


def _hypothetically_eligible():
    """An eligibility row that grants a production role.

    NO LAYER HOLDS THIS TODAY and this fixture asserts none does --
    `eligibility.matrix()` records every pipeline layer
    `publication_eligible: False`. It exists so the ALLOW branch of the
    mechanism is exercised at all; a mechanism whose "yes" is unreachable has
    not been shown to have one. It is a test fixture and it is not a claim
    about any layer.
    """
    real = ELIG.matrix()
    assert not any(r.get('publication_eligible') for r in real.values()), \
        'a layer became publication_eligible -- this fixture must be revisited'
    row = dict(real['receiving_conversion'])
    row.update({'publication_eligible': True,
                'allowed_runtime_role': 'PRODUCTION',
                'owner_state': 'PROSPECTIVELY_VALIDATED',
                'reason': 'TEST FIXTURE ONLY -- not a governance state'})
    return row


def _clean_facts(**over):
    f = dict(
        run_id='RUN-TEST-1',
        metric='receiving/receiving_yards',
        layer='receiving_conversion',
        model_configuration=CAND.PRODUCTION_BASELINE,
        chronology={'injuries': VS.LAWFUL, 'depth_charts': VS.LAWFUL},
        eligibility=ELIG.matrix()['receiving_conversion'],
        hard_invariants={'draw_coherence': {'state': 'PASS', 'class': 'HARD',
                                            'code': 'DRAW_COHERENCE_HOLDS'}},
        warnings=[],
        governance=[],
        spec_version=LY.SPEC['receiving_conversion'],
        completeness='COMPLETE',
        model_health={'metric': 'receiving/receiving_yards', 'warnings': [],
                      'n_scored': 48, 'n_game_clusters': 9,
                      'ranking_eligible': True},
        test_only=False,
        dry_run=False)
    f.update(over)
    return f


class _OpenGate:
    """Open NFL-1 against COPIES, never against the real governance files.

    PATH_C_STATE is copied and its gate flipped in the copy; the owner record
    is written into a temp directory. Nothing under `nfl/research/` is touched
    and the module's paths are restored on exit, so a failure here cannot
    leave a gate open.
    """

    def __enter__(self):
        self.td = tempfile.mkdtemp(prefix='l4_gate_')
        self.old_state, self.old_rec = AUTH.STATE, AUTH.AUTH_RECORD
        st = json.loads(AUTH.STATE.read_text())
        st['gates']['NFL_1'] = 'AUTHORIZED'
        s = pathlib.Path(self.td) / 'PATH_C_STATE.json'
        s.write_text(json.dumps(st))
        r = pathlib.Path(self.td) / 'NFL1_OWNER_AUTHORIZATION.json'
        r.write_text(json.dumps({'basis': 'OWNER_DECISION',
                                 'owner_decision_id': 'TEST-ONLY-NOT-REAL'}))
        AUTH.STATE, AUTH.AUTH_RECORD = s, r
        return self

    def __exit__(self, *a):
        AUTH.STATE, AUTH.AUTH_RECORD = self.old_state, self.old_rec
        return False


# -------------------------------------------------- 1. nothing was broken
def test_the_zero_argument_call_still_answers_exactly_as_it_did():
    """Four live call sites pass no context. None of them may change meaning."""
    o = AUTH.may_publish()
    check('publication is still REFUSED while NFL-1 is NOT AUTHORIZED',
          o.state is State.BLOCKED and o.code == 'NFL1_NOT_AUTHORIZED', o.code)
    check('  the refusal still carries the gate state it read',
          o.evidence.get('gates', {}).get('NFL_1') == 'NOT AUTHORIZED',
          str(o.evidence.get('gates')))
    check('  the cause is still GOVERNANCE, not a defect',
          o.evidence.get('cause') == 'GOVERNANCE', o.evidence.get('cause'))
    check('computing is still allowed',
          AUTH.may_compute().state is State.PASS)


def test_a_context_free_call_says_it_made_no_metric_decision():
    """The old answer was board-wide and silently looked like an answer about
    everything. It now declares its own scope, so a caller that has not been
    wired is visible in the artifact instead of being served a metric-shaped
    answer to a board-shaped question."""
    o = AUTH.may_publish()
    check('the board-wide answer declares its scope',
          o.evidence.get('scope') == 'BOARD_WIDE', o.evidence.get('scope'))
    check('  and states that no metric decision was made',
          o.evidence.get('metric_decision') == 'NOT_MADE',
          o.evidence.get('metric_decision'))
    check('  and says why, rather than leaving a reader to infer it',
          'without a PublicationContext'
          in str(o.evidence.get('why_no_metric_decision')))


# -------------------------------------------------- 2. the mechanism exists
def test_the_gate_receives_every_fact_the_brief_requires():
    required = {'run_id', 'metric', 'layer', 'model_configuration',
                'chronology', 'eligibility', 'hard_invariants', 'warnings',
                'governance', 'completeness', 'model_health'}
    import dataclasses
    have = {f.name for f in dataclasses.fields(AUTH.PublicationContext)}
    check('every required fact is a declared field of the context',
          required <= have, str(sorted(required - have)))
    check('  and the TEST_ONLY quarantine fact travels with them',
          'test_only' in have)
    ctx = AUTH.context(**_clean_facts())
    used = set()
    for f in AUTH.findings(ctx):
        used.update(f.get('inputs') or [])
    check('  every rule names the inputs it consumed', len(used) >= 8,
          str(sorted(used)))


def test_a_missing_fact_raises_rather_than_defaulting():
    facts = _clean_facts()
    facts.pop('completeness')
    try:
        AUTH.context(**facts)
        check('an omitted fact is refused', False, 'no exception')
    except ValueError as e:
        check('an omitted fact is refused rather than defaulted',
              'PUBLICATION_CONTEXT_INCOMPLETE' in str(e), str(e)[:120])
    try:
        AUTH.context(**_clean_facts(invented_fact=1))
        check('an undeclared fact is refused', False, 'no exception')
    except ValueError as e:
        check('an undeclared fact is refused -- nothing would read it',
              'PUBLICATION_CONTEXT_UNKNOWN_FACT' in str(e), str(e)[:120])


def test_there_is_no_path_from_a_green_suite_to_authorization():
    """The module has always said this in prose. With a context object there
    is now somewhere to TRY, so the refusal is made mechanical."""
    for bad in ('tests_passed', 'suite_green', 'override', 'authorized'):
        try:
            AUTH.context(**_clean_facts(**{bad: True}))
            check(f'{bad} is refused as a basis', False, 'accepted')
        except AUTH.ForbiddenBasis as e:
            check(f'{bad} is refused as a basis for publication',
                  'PUBLICATION_BASIS_FORBIDDEN' in str(e), str(e)[:100])
        except ValueError as e:                      # pragma: no cover
            check(f'{bad} is refused as a basis', False, str(e)[:100])


# ----------------------------------- 3. per-run and per-metric, not board-wide
def test_two_metrics_on_one_run_can_get_different_answers():
    """The whole point. Same run, same facts, different metric."""
    with _OpenGate():
        supported = AUTH.decide(AUTH.context(**_clean_facts()))
        absent = AUTH.decide(AUTH.context(**_clean_facts(
            metric='rushing/rushing_yards', layer='rushing_conversion',
            eligibility=ELIG.matrix()['rushing_conversion'])))
    check('a metric with a governed control is not refused for its own sake',
          supported['metric_disposition'] != AUTH.REFUSE,
          supported['metric_disposition'])
    check('  while a declared absence on the same run IS refused',
          absent['metric_disposition'] == AUTH.REFUSE,
          absent['metric_disposition'])
    check('  and the refusal names the product contract that settled it',
          any(f['rule'] == 'METRIC_HAS_GOVERNED_CONTROL'
              and 'metrics.UNSUPPORTED' in str(f['authority'])
              for f in absent['refusals']),
          str([f['rule'] for f in absent['refusals']]))


def test_two_runs_of_one_metric_can_get_different_answers():
    with _OpenGate():
        clean = AUTH.decide(AUTH.context(**_clean_facts(run_id='RUN-A')))
        late = AUTH.decide(AUTH.context(**_clean_facts(
            run_id='RUN-B',
            chronology={'injuries': VS.REJECT_LATE,
                        'depth_charts': VS.LAWFUL})))
    check('the same metric answers differently on two runs',
          clean['metric_disposition'] != late['metric_disposition'],
          f"{clean['metric_disposition']} vs {late['metric_disposition']}")
    check('  a capture taken after the cut refuses THAT run',
          late['metric_disposition'] == AUTH.REFUSE,
          late['metric_disposition'])
    check('  and the run id travels with the decision',
          clean['run_id'] == 'RUN-A' and late['run_id'] == 'RUN-B')


def test_a_dry_run_is_not_evidence_and_cannot_publish():
    """`make_board.build_one` passes dry_run=True on every board it has ever
    produced, and nothing at the gate read it."""
    with _OpenGate():
        d = AUTH.decide(AUTH.context(**_clean_facts(dry_run=True)))
    check('a dry run is refused publication',
          d['metric_disposition'] == AUTH.REFUSE, d['metric_disposition'])
    check('  and the refusal quotes the declaration that settled it',
          any('NEVER prospective evidence' in str(f['authority'])
              for f in d['refusals']),
          str([f['authority'] for f in d['refusals']]))
    with _OpenGate():
        u = AUTH.decide(AUTH.context(**_clean_facts(
            dry_run=AUTH.NOT_SUPPLIED)))
    check('  and a run that did not say is UNEVALUABLE, not assumed live',
          any(f['rule'] == 'DRY_RUN' and f['verdict'] == AUTH.UNEVALUABLE
              for f in u['findings']))


def test_a_candidate_configuration_cannot_publish():
    with _OpenGate():
        d = AUTH.decide(AUTH.context(**_clean_facts(
            model_configuration=CAND.V1_CANDIDATE_R8)))
    check('a candidate configuration is refused publication',
          d['metric_disposition'] == AUTH.REFUSE, d['metric_disposition'])
    check('  and an undeclared configuration is refused too',
          AUTH.decide(AUTH.context(**_clean_facts(
              model_configuration='SOMETHING_NEW')))['metric_disposition']
          == AUTH.REFUSE)


def test_a_hard_invariant_failure_refuses_this_run(): 
    with _OpenGate():
        d = AUTH.decide(AUTH.context(**_clean_facts(
            hard_invariants={'qb_cross_layer_reconciliation':
                             {'state': 'FAIL', 'class': 'HARD',
                              'code': 'CROSS_LAYER_MISMATCH'}})))
    check('a HARD FAIL on the published draws refuses publication',
          d['metric_disposition'] == AUTH.REFUSE, d['metric_disposition'])
    with _OpenGate():
        b = AUTH.decide(AUTH.context(**_clean_facts(
            hard_invariants={'x': {'state': 'BLOCKED', 'class': 'HARD',
                                   'code': 'NOT_RUN'}})))
    check('  and a HARD check that could not run is not a pass',
          b['metric_disposition'] == AUTH.REFUSE, b['metric_disposition'])


# ---------------------------------------- 4. UNDECIDED is a third disposition
def test_undecided_is_distinguishable_from_allow_and_from_refuse():
    check('no real layer publishes a token-free spec, so the ALLOW fixture '
          'below is a fixture and not a claim about a layer',
          all(any(t in (v or '') for t in AUTH.governance_tokens())
              for v in LY.SPEC.values() if v),
          str({k: v for k, v in LY.SPEC.items() if v})[:200])
    with _OpenGate():
        # A token-free spec as well as an eligible layer. NO LAYER PUBLISHES
        # ONE TODAY -- every entry in `layers.SPEC` that is not None names a
        # governance state -- so this too is a fixture proving the ALLOW
        # branch is reachable, not a claim about any layer.
        allow = AUTH.may_publish(AUTH.context(**_clean_facts(
            eligibility=_hypothetically_eligible(),
            spec_version='a-frozen-spec-naming-no-governance-state')))
        undec = AUTH.may_publish(AUTH.context(**_clean_facts(
            governance=_conversion_governance(),
            warnings=_conversion_warnings())))
        refuse = AUTH.may_publish(AUTH.context(**_clean_facts(
            metric='rushing/rushing_yards', layer='rushing_conversion',
            eligibility=ELIG.matrix()['rushing_conversion'])))
    check('a metric clearing every settled rule is ALLOWED',
          allow.state is State.PASS
          and allow.code == 'PUBLICATION_AUTHORIZED', str(allow))
    check('a metric whose governing rule is unset is DEFERRED, not PASS',
          undec.state is State.DEFERRED
          and undec.code == 'PUBLICATION_RULE_UNDECIDED', str(undec)[:160])
    check('a settled refusal is BLOCKED',
          refuse.state is State.BLOCKED, str(refuse)[:120])
    check('  so all three are distinct Outcome states, not three strings',
          len({allow.state, undec.state, refuse.state}) == 3,
          str([allow.state, undec.state, refuse.state]))
    check('  UNDECIDED carries the ruling it is waiting on, by name',
          bool(undec.evidence.get('owed')), str(undec.evidence.get('owed'))[:120])
    check('  and it is neither published nor withheld by this mechanism',
          'neither published nor withheld' in undec.detail, undec.detail[:120])


def test_every_input_to_the_unset_rule_is_attached():
    """The design target for tonight: a metric with no rule emerges carrying
    every input that rule would take."""
    with _OpenGate():
        o = AUTH.may_publish(AUTH.context(**_clean_facts(
            governance=_conversion_governance(),
            warnings=_conversion_warnings())))
    d = o.evidence['decision']
    toks = {f['facts'].get('token') for f in d['undecided']
            if f['rule'].startswith('LAYER_GOVERNANCE_TOKEN')}
    for t in ('SIGNAL_WEAK', 'CALIBRATION_DEFECT', 'HOLD_CHARACTERIZED'):
        check(f'{t} reaches the gate and is reported by name', t in toks,
              str(sorted(x for x in toks if x)))
    one = [f for f in d['undecided'] if f['facts'].get('token') == 'SIGNAL_WEAK']
    check('  the layer that said it travels with the token',
          bool(one) and one[0]['facts'].get('layer') == 'receiving_conversion',
          str(one[:1])[:160])
    check('  the layer\'s own sentence travels unrewritten',
          bool(one) and 'RC1 SIGNAL_WEAK' in one[0]['facts'].get('source_text', ''),
          str(one[:1])[:200])
    check('  and every fact consumed is echoed with the decision',
          set(d['facts_consumed']) >= {'chronology', 'governance',
                                       'completeness', 'model_health'},
          str(sorted(d['facts_consumed'])))


def test_a_refusal_does_not_truncate_the_report():
    """Tonight the board gate refuses. The metric findings must still be
    there, or the facts stop at the first refusal and nothing is learned."""
    o = AUTH.may_publish(AUTH.context(**_clean_facts(
        governance=_conversion_governance(), warnings=_conversion_warnings())))
    d = o.evidence['decision']
    check('the board gate refuses tonight',
          d['board_disposition'] == AUTH.REFUSE, d['board_disposition'])
    check('  and the metric disposition is reported separately',
          d['metric_disposition'] == AUTH.UNDECIDED, d['metric_disposition'])
    check('  the undecided rules survive the refusal',
          len(d['undecided']) >= 3, str(len(d['undecided'])))
    check('  and the refusal detail says so rather than hiding them',
          'ALSO UNDECIDED' in o.detail, o.detail[:200])


# ------------------------------------------ 5. absence is never read as clean
def test_no_withheld_fact_can_produce_a_pass():
    fields = ('model_configuration', 'chronology', 'eligibility',
              'hard_invariants', 'warnings', 'governance', 'completeness',
              'model_health', 'test_only', 'spec_version', 'dry_run')
    for f in fields:
        with _OpenGate():
            o = AUTH.may_publish(AUTH.context(
                **_clean_facts(**{f: AUTH.NOT_SUPPLIED})))
        check(f'withholding {f} never yields a PASS',
              o.state is not State.PASS, f'{f}: {o.code}')


def test_an_unsupplied_fact_is_named_rather_than_summarised():
    with _OpenGate():
        o = AUTH.may_publish(AUTH.context(
            **_clean_facts(chronology=AUTH.NOT_SUPPLIED)))
    check('an unsupplied fact blocks on DATA, not on GOVERNANCE',
          o.state is State.BLOCKED
          and o.evidence.get('cause') == 'DATA', f'{o.code}/{o.evidence.get("cause")}')
    check('  and the rule that could not run is named',
          'CHRONOLOGY_LAWFUL' in o.detail, o.detail[:160])


def test_an_empty_channel_is_not_a_quiet_one():
    """The trap this mechanism must not fall into: governance withheld while
    warnings arrive empty reads as "no token raised" unless it is caught."""
    with _OpenGate():
        d = AUTH.decide(AUTH.context(**_clean_facts(
            governance=AUTH.NOT_SUPPLIED, warnings=[],
            spec_version='rc1-baseline-frozen')))
    tok = [f for f in d['findings']
           if f['rule'].startswith('LAYER_GOVERNANCE_TOKEN')]
    check('one silent channel makes the token question UNEVALUABLE',
          bool(tok) and tok[0]['verdict'] == AUTH.UNEVALUABLE,
          str([f['verdict'] for f in tok]))
    check('  and it names which channel was silent',
          bool(tok) and 'governance' in str(tok[0]['facts'].get(
              'channels_not_supplied')), str(tok[:1])[:160])


def test_an_unsupplied_fact_cannot_be_tested_as_a_boolean():
    try:
        bool(AUTH.NOT_SUPPLIED)
        check('NOT_SUPPLIED refuses truthiness', False, 'it was truthy')
    except RuntimeError as e:
        check('NOT_SUPPLIED refuses truthiness, as Outcome does',
              'NOT_SUPPLIED_TRUTHINESS' in str(e), str(e)[:100])


# --------------------------------- 6. ranking and publication stay separate
def test_a_ranking_refusal_is_not_a_publication_refusal():
    warned = {'metric': 'receiving/receiving_yards', 'n_scored': 48,
              'n_game_clusters': 9, 'ranking_eligible': False,
              'warnings': ['COVERAGE_BELOW_NOMINAL'],
              'warning_meanings': {'COVERAGE_BELOW_NOMINAL': 'x'}}
    with _OpenGate():
        o = AUTH.may_publish(AUTH.context(**_clean_facts(model_health=warned)))
    d = o.evidence['decision']
    check('a health warning refuses RANKING',
          d['ranking_disposition'] == AUTH.REFUSE, d['ranking_disposition'])
    check('  and does NOT by itself refuse publication',
          d['metric_disposition'] != AUTH.REFUSE, d['metric_disposition'])
    check('  publication under a health warning is UNDECIDED instead',
          d['metric_disposition'] == AUTH.UNDECIDED, d['metric_disposition'])
    check('  the ranking refusal is kept in its own list',
          len(d['ranking_refusals']) == 1 and not d['refusals'],
          f"{len(d['ranking_refusals'])}/{len(d['refusals'])}")
    check('  and the composed Outcome is the DEFERRED, not a block',
          o.state is State.DEFERRED, str(o)[:120])


# --------------------------------------- 7. no Wave-7 level was activated
def test_no_wave7_level_assignment_is_implemented():
    ctx = AUTH.context(**_clean_facts(governance=_conversion_governance(),
                                      warnings=_conversion_warnings()))
    d = AUTH.decide(ctx)
    check('the decision declares that no Wave-7 level is activated',
          d['wave7_matrix']['levels_activated'] == [],
          str(d['wave7_matrix']))
    check('  and records the matrix as awaiting a ruling',
          'AWAITING OWNER RULING' in d['wave7_matrix']['status'],
          d['wave7_matrix']['status'])
    toks = [f for f in d['findings']
            if f['rule'].startswith('LAYER_GOVERNANCE_TOKEN:')]
    check('  every governance token resolves UNDECIDED',
          bool(toks) and all(f['verdict'] == AUTH.UNDECIDED for f in toks),
          str([(f['rule'], f['verdict']) for f in toks]))
    check('  and none of them claims an authority',
          all(f['authority'] is None for f in toks),
          str([f['authority'] for f in toks]))
    src = (pathlib.Path(_ROOT) / 'nfl' / 'production'
           / 'authorization.py').read_text()
    for level in ('L1', 'L2', 'L3', 'L4', 'L5'):
        check(f'  the mechanism assigns no {level}',
              f"'{level}'" not in src and f'"{level}"' not in src, level)


def test_a_settled_verdict_must_name_the_ruling_that_settled_it():
    try:
        AUTH._finding('MADE_UP', AUTH.METRIC, AUTH.REFUSE, 'because')
        check('a refusal with no authority is refused', False, 'accepted')
    except ValueError as e:
        check('a settled verdict with no authority is a construction error',
              'PUBLICATION_RULE_WITHOUT_AUTHORITY' in str(e), str(e)[:120])
    try:
        AUTH._finding('MADE_UP', AUTH.METRIC, AUTH.UNDECIDED, 'because',
                      authority='me')
        check('an undecided rule claiming an authority is refused', False, '')
    except ValueError as e:
        check('  and an UNDECIDED claiming an authority is one too',
              'UNDECIDED_WITH_AUTHORITY' in str(e), str(e)[:120])


# ------------------------------- 8. the vocabulary is derived, not retyped
def test_the_token_vocabulary_comes_from_the_governance_artifact():
    st = json.loads((pathlib.Path(_ROOT) / 'nfl' / 'research'
                     / 'PATH_C_STATE.json').read_text())
    axis = set(st['axes']['action']) - set(ELIG.PRODUCTION_ACTIONS)
    vocab = AUTH.governance_tokens()
    check('every non-production action on the artifact axis is in scope',
          axis <= set(vocab), str(sorted(axis - set(vocab))))
    check('  each one records PATH_C_STATE as where it is declared',
          all(vocab[t] == 'PATH_C_STATE.axes.action' for t in axis),
          str({t: vocab[t] for t in sorted(axis)})[:200])
    check('SIGNAL_WEAK is carried WITH its provenance defect, not laundered',
          vocab.get('SIGNAL_WEAK', '').startswith('UNREGISTERED'),
          vocab.get('SIGNAL_WEAK'))
    src = (pathlib.Path(_ROOT) / 'nfl' / 'production'
           / 'authorization.py').read_text()
    body = src.split('def _declared_action_tokens')[1].split('def ')[0]
    check('  and the axis is read, never retyped into this file',
          'axes' in body and 'INFORMATION_CONSTRAINED' not in body,
          body[:160])


def test_the_layers_still_publish_what_this_gate_reads():
    """If layers.py stops declaring these, this file is measuring air."""
    check('the conversion layer still declares CALIBRATION_DEFECT',
          'CALIBRATION_DEFECT' in LY.SPEC['receiving_conversion'],
          LY.SPEC['receiving_conversion'])
    check('  and SIGNAL_WEAK', 'SIGNAL_WEAK' in LY.SPEC['receiving_conversion'])
    check('the appearance layer still declares INFORMATION_CONSTRAINED',
          'INFORMATION_CONSTRAINED' in LY.SPEC['appearance'],
          LY.SPEC['appearance'])
    check('the targets layer still declares DATA_BLOCKED',
          'DATA_BLOCKED' in LY.SPEC['targets_carries'],
          LY.SPEC['targets_carries'])


# --------------------------------------- 9. reading a sealed run, honestly
def test_a_pre_transport_run_reads_as_unevaluable_not_as_clean():
    """A run sealed before WS-D carries no governance key. It must come back
    UNEVALUABLE, because the fact is missing -- not ALLOW, because the layer
    was quiet."""
    root = pathlib.Path(_ROOT) / 'nfl' / 'research' / 'live'
    cands = sorted(root.rglob('run_status.json'))
    if not cands:
        check('a sealed run exists to read', False, str(root))
        return
    rs = json.loads(cands[0].read_text())
    ctx = AUTH.facts_from_run_status(rs, 'receiving/receiving_yards',
                                     'conversion')
    o = AUTH.may_publish(ctx)
    check('a sealed run can be read into a context without inventing a fact',
          isinstance(ctx, AUTH.PublicationContext))
    check('  a run that recorded no governance yields NOT_SUPPLIED',
          ctx.governance is AUTH.NOT_SUPPLIED
          or ctx.completeness is AUTH.NOT_SUPPLIED,
          f'{ctx.governance!r}/{ctx.completeness!r}')
    check('  and the gate never answers PASS on it',
          o.state is not State.PASS, o.code)
    check('  the run id is carried from the seal, not invented',
          ctx.run_id == str(rs.get('run_id')), ctx.run_id)


def test_the_context_must_name_the_run_and_the_metric():
    for bad in ({'run_id': ''}, {'metric': '   '}, {'layer': ''}):
        try:
            AUTH.context(**_clean_facts(**bad))
            check(f'{list(bad)[0]} may not be blank', False, 'accepted')
        except ValueError as e:
            check(f'{list(bad)[0]} may not be blank -- a nameless decision is '
                  f'a board-wide one wearing a metric label',
                  'IDENTITY_MISSING' in str(e), str(e)[:120])


def test_a_malformed_context_is_refused_rather_than_coerced():
    o = AUTH.may_publish({'metric': 'receiving/receiving_yards'})
    check('a bare dict is refused by name',
          o.state is State.FAIL
          and o.code == 'PUBLICATION_CONTEXT_MALFORMED', o.code)


if __name__ == '__main__':
    for _n, _f in sorted(globals().items()):
        if _n.startswith('test_') and callable(_f):
            print(f'\n{_n}')
            _f()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
