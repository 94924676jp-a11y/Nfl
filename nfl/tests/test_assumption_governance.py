"""An assumption can be measured, falsified, and made to block a promotion.

THE ONE CHECK THIS MODULE EXISTS FOR IS `test_F`: running the whole audit
leaves CS2's output BYTE-IDENTICAL. A governance layer that quietly corrects
the thing it audits is worse than no governance layer, because the corrected
number then has no provenance and no one can reproduce the original.

Everything else here supports that: the falsifier was written before the test
(test_C), it is applied as written (test_D), the status only moves on a legal
edge with evidence (test_B), and the block reaches the real production path
rather than a parallel one (test_G).
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance import assumption as AS                 # noqa: E402
from sportsplatform.governance.outcome import State                    # noqa: E402
from nfl.production.assumptions import audit_appearance as AA          # noqa: E402
from nfl.production.assumptions import registry as REG                 # noqa: E402
from nfl.production.assumptions import run_audit as RUN                # noqa: E402
from nfl.research.assumptions import a2_redistribution as A2R          # noqa: E402
from nfl.production import adjustment_registry as ADJ                  # noqa: E402

PASSED = 0
FAILED = 0
NOT_EXECUTED = []

ART = _REPO/'nfl/research/assumptions/ASSUMPTION_AUDIT.json'
A1 = 'A1_APPEARANCE_CERTAINTY'


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


def _valid(**kw):
    base = dict(id='T', claim='c' * 20, estimand='e' * 20,
                population='p' * 20, test='m.f',
                falsifier='the rate is below one with an interval excluding '
                          'it, or any member is observed failing',
                downstream_dependencies=('consumer',),
                criticality=AS.MATERIAL, status=AS.DECLARED)
    base.update(kw)
    return AS.Assumption(**base)


def test_A_the_schema_requires_every_field_that_makes_it_actionable():
    check('A a complete record validates',
          AS.validate(_valid()).state is State.PASS)
    for field, bad in (('claim', ''), ('estimand', ''), ('population', ''),
                       ('test', ''), ('falsifier', ''),
                       ('downstream_dependencies', ())):
        o = AS.validate(_valid(**{field: bad}))
        check(f'A an empty {field} is refused',
              o.state is State.FAIL and o.code == AS.CODE_INVALID,
              f'{o.state}[{o.code}]')
    o = AS.validate(_valid(status=AS.SUPPORTED, evidence={}))
    check('A SUPPORTED with no evidence is refused',
          o.state is State.FAIL, f'{o.state}[{o.code}]')
    o = AS.validate(_valid(criticality='VERY'))
    check('A an invented criticality is refused', o.state is State.FAIL)


def test_B_status_moves_only_on_a_legal_edge_and_only_with_evidence():
    a = _valid()
    o = AS.settle(a, status=AS.FALSIFIED, evidence={})
    check('B a move with no evidence is refused',
          o.state is State.FAIL and o.code == AS.CODE_BAD_MOVE,
          f'{o.state}[{o.code}]')
    o = AS.settle(a, status=AS.FALSIFIED, evidence={'n': 5})
    check('B DECLARED -> FALSIFIED with evidence is allowed',
          o.state is State.PASS, f'{o.state}[{o.code}]')
    back = AS.settle(o.value, status=AS.DECLARED, evidence={'n': 5})
    check('B but nothing may move BACK to DECLARED',
          back.state is State.FAIL and back.code == AS.CODE_BAD_MOVE,
          f'{back.state}[{back.code}]')
    w = AS.settle(o.value, status=AS.WITHDRAWN, evidence={'n': 5})
    check('B WITHDRAWN is terminal',
          w.state is State.PASS
          and AS.settle(w.value, status=AS.SUPPORTED,
                        evidence={'n': 5}).state is State.FAIL)
    check('B and settling never edits the falsifier',
          o.evidence['falsifier_unchanged'] is True)


def test_C_the_registry_is_seeded_and_every_falsifier_is_concrete():
    o = REG.audit()
    check('C the registry validates', o.state is State.PASS,
          f'{o.state}[{o.code}] {o.detail}')
    check('C five assumptions are seeded', len(REG.REGISTRY) == 5,
          str(len(REG.REGISTRY)))
    ids = {a.id for a in REG.REGISTRY}
    check('C including the four named successors',
          {'A2_PROPORTIONAL_REDISTRIBUTION',
           'A3_ROLE_CONTINUITY_ACROSS_REGIME_CHANGE',
           'A4_STATIC_TEAM_VOLUME_SUFFICIENCY',
           'A5_TD_CONVERSION_PORTABILITY'} <= ids, str(sorted(ids)))
    check('C every one names what depends on it',
          all(a.downstream_dependencies for a in REG.REGISTRY))
    check('C and v0 declares that it has no source scanner',
          'no automatic source-code' in o.evidence['no_source_scanner_yet'])


def test_D_the_boundary_band_is_derived_from_the_sampler():
    check('D the band is one expected occurrence across the worlds',
          AA.band(8000) == 1.0 / 8000 and AA.band(1000) == 1e-3,
          str(AA.band(8000)))
    check('D so a bigger simulation gives a TIGHTER band',
          AA.band(80000) < AA.band(8000))
    o = AA.audit({'a': 0.5, 'b': 0.2}, n_draws=8000)
    check('D interior probabilities pass', o.state is State.PASS,
          f'{o.state}[{o.code}]')
    o = AA.audit({'a': 1.0, 'b': 0.5}, n_draws=8000)
    check('D an exact 1.0 is caught',
          o.state is State.FAIL and o.code == AA.CODE
          and o.evidence['n_exactly_one'] == 1, f'{o.state}[{o.code}]')
    o = AA.audit({'a': 1 - 1e-6, 'b': 0.5}, n_draws=8000)
    check('D and so is a value the sampler cannot tell from 1.0',
          o.state is State.FAIL and o.evidence['n_near_one'] == 1,
          str(o.evidence['n_near_one']))
    # AND THE DIRECTION MATTERS, so it is asserted rather than assumed. More
    # draws RESOLVE more, so the same probability can be indistinguishable
    # from certainty at 8,000 worlds and interior at 80,000. (An earlier
    # version of this check had it backwards and expected a 100-draw run to
    # be more discriminating, which is exactly wrong.)
    p = 1 - 5e-5
    small = AA.audit({'a': p, 'b': 0.5}, n_draws=8000)
    big = AA.audit({'a': p, 'b': 0.5}, n_draws=80000)
    check('D the same p is near-boundary at 8,000 draws and interior at '
          '80,000', small.state is State.FAIL and big.state is State.PASS,
          f'{small.code} / {big.code}')
    o = AA.audit({'a': 1.5}, n_draws=8000)
    check('D a value outside [0,1] is an arithmetic error, not a boundary',
          o.code == 'APPEARANCE_PROBABILITY_OUT_OF_RANGE', o.code)
    check('D and the audit says it does not clip',
          'does not floor' in AA.audit({'a': 0.5}, n_draws=8000)
          .evidence['nothing_is_clipped'])


def test_E_a1_was_falsified_by_measurement_as_written():
    if not ART.exists():
        NOT_EXECUTED.append('E audit artifact absent')
        return
    d = json.loads(ART.read_text())
    a1 = next(a for a in d['registry']['assumptions'] if a['id'] == A1)
    check('E A1 is FALSIFIED', a1['status'] == AS.FALSIFIED, a1['status'])
    check('E it is CRITICAL', a1['criticality'] == AS.CRITICAL)
    ev = a1['evidence']
    check('E the cohort rate is far below the asserted 1.0',
          ev['rate'] < 0.99, str(ev['rate']))
    check('E on a real sample, with an interval',
          ev['n'] > 1000 and ev['ci95'][1] < 1.0,
          f"n={ev['n']} ci={ev['ci95']}")
    check('E both falsifier limbs fired, and were recorded separately',
          ev['limb_upper_bound_below_one'] is True
          and ev['limb_any_observed_failure'] is True, str(ev))
    check('E the settlement did not edit the falsifier',
          d['settlement']['falsifier_unchanged'] is True)
    check('E and the live model really does assert certainty',
          d['boundary_audit']['evidence']['n_exactly_one'] > 0,
          str(d['boundary_audit']['evidence']['n_exactly_one']))


def test_F_the_audit_does_not_rewrite_the_model_output():
    """The check this module exists for."""
    before = RUN.live_appearance()
    if before.state is not State.PASS:
        NOT_EXECUTED.append('F byte-identity (CS2 state unavailable)')
        return

    def digest(o):
        return hashlib.sha256(json.dumps(
            {f'{k[0]}:{k[1]}': r for k, r in o.value.items()},
            sort_keys=True, default=str).encode()).hexdigest()

    h0 = digest(before)
    body = RUN.run()
    after = RUN.live_appearance()
    h1 = digest(after)
    check('F CS2 output is byte-identical after the whole audit runs',
          h0 == h1, f'{h0[:16]} vs {h1[:16]}')
    check('F and the audit says so itself',
          'no probability is clipped' in body['nothing_is_repaired'])
    n1 = sum(1 for r in after.value.values() if r['p_appears'] >= 1.0)
    check('F the saturated rows are still saturated, not quietly floored',
          n1 > 0, str(n1))
    check('F the audit still reports them',
          body['boundary_audit']['evidence']['n_exactly_one'] == n1,
          f"{body['boundary_audit']['evidence']['n_exactly_one']} vs {n1}")


def test_G_a_falsified_critical_assumption_blocks_promotion():
    a = _valid(id='CRIT', criticality=AS.CRITICAL)
    ok = AS.assert_promotable([a], consumer='consumer', require_tested=False)
    check('G DECLARED does not block when tested is not required',
          ok.state is State.PASS, f'{ok.state}[{ok.code}]')
    strict = AS.assert_promotable([a], consumer='consumer',
                                  require_tested=True)
    check('G but an untested CRITICAL blocks when it is required',
          strict.state is State.FAIL and strict.code == AS.CODE_UNTESTED,
          f'{strict.state}[{strict.code}]')
    bad = AS.settle(a, status=AS.FALSIFIED, evidence={'n': 9}).value
    o = AS.assert_promotable([bad], consumer='consumer')
    check('G a falsified CRITICAL blocks',
          o.state is State.FAIL and o.code == AS.CODE_BLOCKED,
          f'{o.state}[{o.code}]')
    check('G and the refusal says the output is unchanged',
          'model output is unchanged' in o.detail, o.detail[:90])
    other = AS.assert_promotable([bad], consumer='someone_else')
    check('G a consumer that does not depend on it is NOT blocked',
          other.state is State.PASS, f'{other.state}[{other.code}]')
    mat = AS.settle(_valid(id='MAT', criticality=AS.MATERIAL),
                    status=AS.FALSIFIED, evidence={'n': 9}).value
    warn = AS.assert_promotable([mat], consumer='consumer')
    check('G a falsified MATERIAL warns rather than blocking',
          warn.state is State.PASS
          and warn.evidence['falsified_material'] == ['MAT'],
          f'{warn.state} {warn.evidence["falsified_material"]}')


def test_H_the_block_reaches_the_real_production_path():
    """Not a parallel gate: the one adjustment_registry already enforces."""
    check('H the adjustment registry has an assumption gate',
          hasattr(ADJ, '_assumption_gate'))
    g = ADJ._assumption_gate('nfl.production.nonqb.cs2_state', ADJ.PRODUCTION)
    check('H which blocks the layer A1 depends on',
          g is not None and g.state is State.FAIL
          and g.code == AS.CODE_BLOCKED,
          f'{g.code if g is not None else "no gate"}')
    g2 = ADJ._assumption_gate('team_volume', ADJ.PRODUCTION)
    check('H and does not block a layer no falsified assumption names',
          g2 is not None and g2.state is State.PASS,
          f'{g2.code if g2 is not None else "no gate"}')
    g3 = ADJ._assumption_gate('nfl.production.nonqb.cs2_state', ADJ.RESEARCH)
    check('H research purpose is not gated by it', g3 is None)


def test_I_a_measured_status_is_overlaid_not_hand_edited():
    """The registry DECLARES; the artifact RECORDS. Neither can do the other."""
    declared = {a.id: a.status for a in REG.REGISTRY}
    live = {a.id: a.status for a in REG.all_assumptions()}
    check('I every declared status in code is DECLARED',
          set(declared.values()) == {AS.DECLARED}, str(set(declared.values())))
    check('I while the live view carries the measured falsification',
          live[A1] == AS.FALSIFIED, live[A1])
    check('I and the falsifier text is still the code\'s, not the artifact\'s',
          REG.get(A1).falsifier
          == next(a for a in REG.all_assumptions() if a.id == A1).falsifier)
    # A corrupt artifact must not be able to promote anything.
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d)/'forged.json'
        p.write_text(json.dumps({'registry': {'assumptions': [
            {'id': A1, 'status': AS.SUPPORTED, 'evidence': {}}]}}))
        forged = {a.id: a.status for a in REG.all_assumptions(p)}
        check('I a forged SUPPORTED with no evidence is ignored',
              forged[A1] == AS.DECLARED, forged[A1])
        p.write_text(json.dumps({'registry': {'assumptions': [
            {'id': A1, 'status': 'INVENTED', 'evidence': {'n': 1}}]}}))
        forged = {a.id: a.status for a in REG.all_assumptions(p)}
        check('I and a status off the transition graph is ignored too',
              forged[A1] == AS.DECLARED, forged[A1])


A2 = 'A2_PROPORTIONAL_REDISTRIBUTION'
A2_ART = _REPO/'nfl/research/assumptions/A2_REDISTRIBUTION.json'


def test_J_the_a2_cohort_is_built_the_way_it_says_it_is():
    if not A2_ART.exists():
        NOT_EXECUTED.append('J A2 artifact absent')
        return
    d = json.loads(A2_ART.read_text())
    ev = d['evidence']
    check('J thresholds were declared and travel with the result',
          set(ev['thresholds']) >= {'MIN_SHARE', 'WINDOW', 'MIN_SURVIVORS',
                                    'MIN_VOLUME', 'MIN_CELL'},
          str(ev['thresholds']))
    check('J multi-shock weeks were excluded and counted',
          ev['skipped'].get('multi_shock', 0) > 0
          and 'attributed' in ev['multi_shock_excluded_because'],
          str(ev['skipped'].get('multi_shock')))
    check('J the ordinal guard recorded zero violations',
          '0 violations' in ev['ordinal_guard'], ev['ordinal_guard'])
    check('J routes and pass participation are refused, with the reason',
          set(ev['rooms_not_available']) == {'routes', 'pass_snaps'}
          and 'not captured' in ev['rooms_not_available']['routes'],
          str(sorted(ev['rooms_not_available'])))
    check('J and no substitution matrix was written',
          'discarded' in ev['no_substitution_matrix_is_written'])


def test_K_room_closure_and_redistribution_are_scored_apart():
    """The decomposition that keeps the answer honest."""
    if not A2_ART.exists():
        NOT_EXECUTED.append('K decomposition')
        return
    d = json.loads(A2_ART.read_text())
    check('K the artifact says why there are two scores',
          'wrong one' in d['evidence']['two_scores_because_two_questions'])
    for room, v in d['rooms'].items():
        arms = v['arms']
        check(f'K {room}: NO_TRANSFER and PROPORTIONAL are the SAME in-room '
              f'rule, so their in-room scores match exactly',
              abs(arms['NO_TRANSFER']['log_score_in_room']
                  - arms['PROPORTIONAL']['log_score_in_room']) < 1e-12,
              f"{arms['NO_TRANSFER']['log_score_in_room']} vs "
              f"{arms['PROPORTIONAL']['log_score_in_room']}")
        check(f'K {room}: and NO_TRANSFER beats it on the TOTAL score, which '
              f'is the room-closure defect, not a redistribution one',
              arms['NO_TRANSFER']['log_score_total']
              < arms['PROPORTIONAL']['log_score_total'],
              f"{arms['NO_TRANSFER']['log_score_total']:.4f} vs "
              f"{arms['PROPORTIONAL']['log_score_total']:.4f}")
    closure = {r: v['room_closure']['mean_share_to_players_outside_the_room']
               for r, v in d['rooms'].items()}
    check('K every room leaks opportunity to players outside it',
          all(x > 0.05 for x in closure.values()),
          str({k: round(v, 4) for k, v in closure.items()}))


def test_L_the_falsifier_fired_on_the_general_limb_and_not_the_specific_one():
    """The named mechanism was wrong, and that is on the record."""
    if not A2_ART.exists():
        NOT_EXECUTED.append('L falsifier limbs')
        return
    ev = json.loads(A2_ART.read_text())['evidence']
    check('L the general limb fires in all four rooms',
          len(ev['falsifier_limb_general_departure']) == 4,
          str(ev['falsifier_limb_general_departure']))
    check('L the specific limb -- nearest neighbour absorbs MORE -- fires in '
          'none', ev['falsifier_limb_nearest_neighbour_absorbs_more'] == [],
          str(ev['falsifier_limb_nearest_neighbour_absorbs_more']))
    check('L A2 is falsified on the general limb', ev['falsifies_a2'] is True)
    check('L and the wrong guess is recorded rather than quietly repaired',
          'close to the opposite' in ev['the_named_mechanism_was_wrong']
          or 'does not' in ev['the_named_mechanism_was_wrong'],
          ev['the_named_mechanism_was_wrong'][:80])
    het = ev['heterogeneity']
    check('L already-larger survivors absorb LESS than proportional',
          all(h['nearest_neighbour_absorbs_more'] is False
              for h in het.values()))


def test_M_the_intervals_are_clustered_by_shock_event():
    if not A2_ART.exists():
        NOT_EXECUTED.append('M clustering')
        return
    d = json.loads(A2_ART.read_text())
    seen = 0
    for room, v in d['rooms'].items():
        for rd, c in v['absorption_by_rank_distance'].items():
            seen += 1
            check_once = (c['n_event_clusters'] <= c['n_survivors']
                          and c['ci95_cluster_bootstrap'][0] is not None
                          and 's_j / (1 - s_i)' in c['null_is'])
            if not check_once:
                check(f'M {room} rd={rd} carries a clustered interval and a '
                      f'stated null', False, str(c))
                return
    check('M every cell carries a cluster-bootstrap interval and states its '
          'null as the proportional prediction', seen > 0, str(seen))
    fewer = [(r, rd) for r, v in d['rooms'].items()
             for rd, c in v['absorption_by_rank_distance'].items()
             if c['n_event_clusters'] < c['n_survivors']]
    check('M and at least one cell really has fewer clusters than survivors, '
          'so the clustering is doing work', bool(fewer), str(fewer[:3]))


def test_N_a2_blocks_only_the_substitution_path():
    if not ART.exists():
        NOT_EXECUTED.append('N A2 promotion scope')
        return
    d = json.loads(ART.read_text())
    a2 = next((a for a in d['registry']['assumptions'] if a['id'] == A2), None)
    check('N A2 is FALSIFIED in the audit', a2 and a2['status'] == AS.FALSIFIED,
          str(a2 and a2['status']))
    blocked = {k for k, v in d['promotion'].items()
               if v['code'] == AS.CODE_BLOCKED}
    check('N the substitution path is blocked',
          {'nfl.production.nonqb.rushing_a1',
           'nfl.production.nonqb.shared_pass'} <= blocked, str(sorted(blocked)))
    check('N and nothing outside it is blocked by A2',
          'nfl.production.nonqb.layers' not in blocked
          and 'nfl.production.nonqb.rushing_conversion' not in blocked
          and 'nfl.research.oas1.baselines' not in blocked,
          str(sorted(blocked)))
    check('N A2 carries its uncertainty as a clustered interval',
          'cluster bootstrap' in (a2.get('uncertainty') or ''),
          str(a2.get('uncertainty')))


def test_O_the_successor_spec_installs_no_numbers():
    spec = _REPO/'nfl/research/assumptions/A2_SUCCESSOR_SPEC.md'
    check('O a successor specification exists', spec.exists())
    if not spec.exists():
        return
    t = spec.read_text()
    check('O it forbids a hand-designed matrix',
          'No hand-designed substitution matrix' in t)
    # Matched on a wrap-proof pair rather than one sentence: the markdown
    # line-wraps, and a test that breaks when a paragraph reflows is testing
    # the formatter.
    flat = ' '.join(t.split())
    check('O it forbids carrying a coefficient over from the diagnosis',
          'No coefficient carried over' in flat
          and 'fitting on the evaluation set' in flat)
    check('O it keeps the proportional allocator in production meanwhile',
          'stays in production until a successor beats it' in t)
    check('O and it declares a measured negative to be a result',
          'measured negative is a result' in t)


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in (test_A_the_schema_requires_every_field_that_makes_it_actionable,
               test_B_status_moves_only_on_a_legal_edge_and_only_with_evidence,
               test_C_the_registry_is_seeded_and_every_falsifier_is_concrete,
               test_D_the_boundary_band_is_derived_from_the_sampler,
               test_E_a1_was_falsified_by_measurement_as_written,
               test_F_the_audit_does_not_rewrite_the_model_output,
               test_G_a_falsified_critical_assumption_blocks_promotion,
               test_H_the_block_reaches_the_real_production_path,
               test_I_a_measured_status_is_overlaid_not_hand_edited,
               test_J_the_a2_cohort_is_built_the_way_it_says_it_is,
               test_K_room_closure_and_redistribution_are_scored_apart,
               test_L_the_falsifier_fired_on_the_general_limb_and_not_the_specific_one,
               test_M_the_intervals_are_clustered_by_shock_event,
               test_N_a2_blocks_only_the_substitution_path,
               test_O_the_successor_spec_installs_no_numbers):
        fn()
    for n in NOT_EXECUTED:
        print(f'  NOT_EXECUTED {n}')
    print(f'\n{PASSED} passed, {FAILED} failed, {len(NOT_EXECUTED)} NOT_EXECUTED')
    raise SystemExit(1 if FAILED else 0)
