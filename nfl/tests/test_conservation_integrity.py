"""One code, one invariant, one producer -- and absence is never a pass.

The conservation audit found OPPORTUNITY_CONSERVATION_FAILURE naming two
producers that do not enforce the same thing. This suite checks the split:
that the three codes fire on their own failure and not on each other's, and
that every way of having no evidence lands on NOT_CHECKED rather than on a
clean result.
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production import conservation_integrity as CI               # noqa: E402
from nfl.production.integrity import contract as IC                   # noqa: E402
from nfl.production.review import gate as GATE                        # noqa: E402
from nfl.production.universe import conservation_bridge as CB         # noqa: E402

PASSED = FAILED = 0


def ok(cond, what):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok     {what}')
    else:
        FAILED += 1
        print(f'  FAIL   {what}')


def cov(report, code):
    for c in report.coverage:
        if c.code == code:
            return c
    return None


def chain(gates):
    return {'layers': {'allocation': {room: {'gate': g}
                                      for room, g in gates.items()}}}


def rs_doc(coherence_code='DRAW_COHERENCE_HOLDS', cert=True, failed=(),
           components=None):
    d = {'draw_coherence': {
        'state': 'FAIL' if coherence_code == CI.COHERENCE_VIOLATED else 'PASS',
        'code': coherence_code, 'detail': 'fixture',
        'components': components if components is not None else {
            'qb': {'state': 'PASS', 'code': 'QB_DRAW_COHERENCE_HOLDS'},
            'receiving': {'state': 'PASS', 'code': 'RECEIVING_COHERENT'}}}}
    if failed:
        d['draw_coherence']['failed'] = list(failed)
    d['coherence_certificate_verdict'] = (
        {'code': CI.CERTIFICATE_VERIFIED, 'state': 'PASS'} if cert
        else {'code': 'COHERENCE_CERTIFICATE_ARRAYS_CHANGED', 'state': 'FAIL'})
    return d


# -- 1. the split ----------------------------------------------------------
def test_the_two_allocation_invariants_do_not_share_a_code():
    ok(CI.C_CONSERVATION != CI.C_CONSUMER_SCOPE,
       'conservation and consumer scope carry different codes')
    ok(CI.PRODUCER_CONSERVATION != CI.PRODUCER_SCOPE,
       'and different producers, so neither can silently decide what the '
       'other means')
    bad = chain({'targets': {'code': CI.ALLOC_FAILS,
                             'offending': [{'club': 'SF',
                                            'kind': 'COMPOSITION_NOT_UNIT',
                                            'sum': 0.98}]}})
    r = CI.allocation_conserves(bad)
    c = cov(r, CI.C_CONSERVATION)
    ok(c.state == IC.CHECKED_AND_FAILING,
       f'a room summing to 0.98 is a conservation failure: {c.state}')
    ok(len(r.findings) == 1 and r.findings[0].subject == 'SF',
       f'naming the club: {r.findings[0].subject}')
    ok('lost or invented opportunity' in r.findings[0].detail,
       'and saying what that means for everything derived from it')

    s = CI.consumer_within_composition(bad)
    sc = cov(s, CI.C_CONSUMER_SCOPE)
    ok(sc.state == IC.NOT_CHECKED,
       f'while SCOPE on the same run is NOT_CHECKED, because the function '
       f'returned before it looked: {sc.state}')
    ok('returned before evaluating scope' in sc.detail,
       'saying exactly that, rather than inferring a pass from a different '
       'check having failed')


def test_a_scope_failure_is_not_a_conservation_failure():
    out = chain({'carries': {
        'code': CI.ALLOC_SCOPE_FAILS,
        'offending': [{'gsis_id': '00-0011', 'display_name': 'A Back',
                       'allocation_state': 'NOT_IN_ROOM'}]}})
    r = CI.allocation_conserves(out)
    ok(cov(r, CI.C_CONSERVATION).state == IC.CHECKED_AND_PASSING
       and not r.findings,
       'CONSUMER_READS_OUTSIDE means conservation PASSED and the function '
       'went on, so conservation is reported passing')
    s = CI.consumer_within_composition(out)
    ok(cov(s, CI.C_CONSUMER_SCOPE).state == IC.CHECKED_AND_FAILING,
       'and the scope invariant is the one that fails')
    ok(s.findings[0].subject == '00-0011'
       and s.findings[0].subject_kind == 'player',
       f'attributed to the player, not to a club: '
       f'{s.findings[0].subject_kind}')
    ok(s.findings[0].code == CI.C_CONSUMER_SCOPE,
       'under its own code')


def test_a_clean_run_passes_both():
    good = chain({'targets': {'code': CI.ALLOC_CONSERVES},
                  'carries': {'code': CI.ALLOC_CONSERVES}})
    for fn, code in ((CI.allocation_conserves, CI.C_CONSERVATION),
                     (CI.consumer_within_composition, CI.C_CONSUMER_SCOPE)):
        r = fn(good)
        c = cov(r, code)
        ok(c.state == IC.CHECKED_AND_PASSING and not r.findings,
           f'{code} passes on two conserving rooms, n_checked='
           f'{c.n_subjects_checked}')


def test_no_consuming_set_conserves_but_does_not_establish_scope():
    out = chain({'targets': {'code': CI.ALLOC_NO_CONSUMER}})
    ok(cov(CI.allocation_conserves(out),
           CI.C_CONSERVATION).state == IC.CHECKED_AND_PASSING,
       'NO_CONSUMING_SET_DECLARED is reached only after conservation held, '
       'so conservation passes')
    ok(cov(CI.consumer_within_composition(out),
           CI.C_CONSUMER_SCOPE).state == IC.NOT_CHECKED,
       'and scope is NOT_CHECKED: the function never reached that branch')


def test_an_unrecognised_allocation_code_is_not_a_pass():
    out = chain({'targets': {'code': 'ALLOCATION_PROBABLY_FINE'}})
    c = cov(CI.allocation_conserves(out), CI.C_CONSERVATION)
    ok(c.state == IC.NOT_CHECKED,
       f'a code this producer has never seen is NOT_CHECKED: {c.state}')
    ok('drifted apart' in c.detail,
       'and is reported as the two sides having drifted, not as a clean run')


# -- 2. draw coherence -----------------------------------------------------
def test_an_impossible_cell_blocks():
    doc = rs_doc(CI.COHERENCE_VIOLATED, failed=['qb'], components={
        'qb': {'state': 'FAIL', 'code': 'QB_COMPLETIONS_EXCEED_ATTEMPTS',
               'violations': {'qb_completions_within_attempts': 5278},
               'cells_checked': {'qb_completions_within_attempts': 992000}}})
    r = CI.draw_coherence(doc)
    ok(cov(r, CI.C_DRAW_COHERENCE).state == IC.CHECKED_AND_FAILING,
       'a published draw matrix with an impossible cell is CHECKED_AND_'
       'FAILING')
    f = r.findings[0]
    ok(f.subject == 'qb' and f.severity == IC.BLOCKING,
       f'naming the component and blocking: {f.subject}')
    ok(f.evidence['violations']['qb_completions_within_attempts'] == 5278,
       'carrying the violation count')
    ok(f.owner == IC.OWNER_SIMULATION,
       f'owned by the simulation artifact, not by the gate: {f.owner}')


def test_a_violation_is_reported_even_without_a_verified_certificate():
    """A violation found on the pre-publication arrays is a violation
    whatever happened next. Only a PASS needs the certificate."""
    r = CI.draw_coherence(rs_doc(CI.COHERENCE_VIOLATED, cert=False,
                                 failed=['receiving']))
    ok(cov(r, CI.C_DRAW_COHERENCE).state == IC.CHECKED_AND_FAILING,
       'the failure still blocks with an unverified certificate')
    ok(r.findings[0].evidence['certificate_verified'] is False,
       'and the certificate state is recorded on the finding')


def test_a_pass_without_a_verified_certificate_is_not_a_pass():
    c = cov(CI.draw_coherence(rs_doc(cert=False)), CI.C_DRAW_COHERENCE)
    ok(c.state == IC.NOT_CHECKED,
       f'coherence holding on arrays nobody proved were the sealed ones is '
       f'NOT_CHECKED: {c.state}')
    ok('overwritten' in c.detail,
       'naming the failure mode -- the guard ran, then its values were '
       'replaced')
    ok(cov(CI.draw_coherence(rs_doc(cert=True)),
           CI.C_DRAW_COHERENCE).state == IC.CHECKED_AND_PASSING,
       'while the same verdict WITH a verified certificate passes, so the '
       'certificate is doing the work and the check is not simply refusing '
       'everything')


def test_every_way_of_having_no_verdict_is_not_checked():
    for doc, label in (
            ({}, 'an empty run_status'),
            ({'draw_coherence': {}}, 'a draw_coherence block with no code'),
            (rs_doc(CI.COHERENCE_NOT_EVALUABLE), 'NOT_EVALUABLE'),
            (rs_doc(CI.COHERENCE_VACUOUS), 'VACUOUS'),
            (rs_doc('DRAW_COHERENCE_SEEMS_OK'), 'an unrecognised code')):
        c = cov(CI.draw_coherence(doc), CI.C_DRAW_COHERENCE)
        ok(c.state == IC.NOT_CHECKED, f'{label} is NOT_CHECKED: {c.state}')
    c = cov(CI.draw_coherence({}), CI.C_DRAW_COHERENCE)
    ok('shared_pass_live' in c.detail,
       'and the empty case explains why the check is not simply re-run here')


def test_it_reads_a_real_sealed_run_status():
    """A producer proved only against fixtures has not been shown to match
    the shape production actually writes."""
    found = None
    for p in sorted(_REPO.glob('nfl/research/**/run_status.json')):
        try:
            j = json.loads(p.read_text())
        except Exception:                                      # noqa: BLE001
            continue
        if isinstance(j.get('draw_coherence'), dict) and \
                j['draw_coherence'].get('code'):
            found = (p, j)
            break
    ok(found is not None,
       'a sealed run_status carrying a draw_coherence verdict exists on disk')
    if found:
        p, j = found
        c = cov(CI.draw_coherence(j), CI.C_DRAW_COHERENCE)
        ok(c.state in (IC.CHECKED_AND_PASSING, IC.CHECKED_AND_FAILING),
           f'and the producer reads it to a real verdict rather than '
           f'NOT_CHECKED: {c.state} from {p.parent.name}')
        ok(c.n_subjects_checked and c.n_subjects_checked > 0,
           f'over {c.n_subjects_checked} recorded component(s)')


# -- 3. the gate registry --------------------------------------------------
def test_the_gate_advertises_only_what_has_a_producer():
    ok(GATE.C_DRAW_COHERENCE in GATE.ADVERTISED_INTEGRITY
       and GATE.C_DRAW_COHERENCE not in GATE.OBSERVED_INTEGRITY,
       'PROMOTED 2026-09-23: for a governed publishable simulation artifact '
       'draw coherence is a required invariant, so it is advertised')
    ok(GATE.ADVERTISED_INTEGRITY[GATE.C_DRAW_COHERENCE]['producer']
       == CI.PRODUCER_COHERENCE,
       'naming this module')
    ok(not (set(GATE.OBSERVED_INTEGRITY) & set(GATE.ADVERTISED_INTEGRITY)),
       'the two registries are disjoint, so no code is both guaranteed and '
       'merely observed')
    ok(GATE.C_DRAW_COHERENCE in GATE.BLOCKING_CODES,
       'and it blocks')
    ok(GATE.C_DRAW_COHERENCE in GATE.MATERIALITY_EXEMPT,
       'whatever its magnitude -- an impossible cell corrupts every number '
       'computed off that matrix')
    for code in (GATE.C_CONSERVATION, GATE.C_CONSUMER_SCOPE):
        ok(code in GATE.RELINQUISHED_CODES,
           f'{code} is still RELINQUISHED, because no chain result reaches '
           f'the review directory')
        ok(code not in GATE.ADVERTISED_INTEGRITY,
           f'and is NOT advertised -- advertising a guarantee production '
           f'does not evaluate is the defect this registry exists to end')
        ok('SEPARATE ENTRY POINT' in
           GATE.RELINQUISHED_CODES[code]['gap'].upper(),
           f'with the real reason recorded: run_chain and run_forecast are '
           f'separate entry points')
    ok('conservation_integrity.allocation_conserves'
       in GATE.RELINQUISHED_CODES[GATE.C_CONSERVATION]['gap'],
       'and the gap says the producer already EXISTS, so the missing piece '
       'is the path and not the code')


def test_the_gate_no_longer_claims_one_code_for_two_invariants():
    entry = GATE.RELINQUISHED_CODES[GATE.C_CONSERVATION]
    ok('draw_coherence.assert_draw_coherence' not in entry['enforced_today'],
       'OPPORTUNITY_CONSERVATION_FAILURE no longer names the draw-coherence '
       'producer: that invariant has its own code now')
    ok(GATE.ADVERTISED_INTEGRITY[GATE.C_DRAW_COHERENCE]['owner']
       != GATE.RELINQUISHED_CODES[GATE.C_CONSERVATION]['owner'],
       'and the two carry different owners -- simulation artifact against '
       'opportunity allocation')


def test_compose_still_refuses_a_code_claimed_twice():
    """The protection that surfaced the whole audit. Not weakened."""
    a = CI.draw_coherence(rs_doc())
    b = CI.draw_coherence(rs_doc())
    try:
        IC.IntegrityReport.compose([a, b])
        ok(False, 'two producers claiming one code should be refused')
    except AssertionError as e:
        ok(GATE.C_DRAW_COHERENCE in str(e),
           'composing two reports that both claim the code is still refused '
           'by name')


# -- 4. applicability -------------------------------------------------------
def test_an_artifact_that_claims_to_be_a_simulation_is_applicable():
    """The rule the owner ruling turns on: an absent array does not buy
    NOT_APPLICABLE. A full NFL simulation carrying no quarterback row is a
    DEFECTIVE simulation, not one the invariant does not apply to."""
    ap = CI.simulation_applicability({'layers': {'receiving': {}}})
    ok(ap.state == IC.APPLICABLE_AND_CHECKED,
       f'an artifact with draw layers but no qb layer is APPLICABLE: '
       f'{ap.state}')
    ap2 = CI.simulation_applicability(None)
    ok(ap2.state == IC.APPLICABLE_AND_CHECKED,
       f'and so is one that declared nothing at all -- silence fails '
       f'closed: {ap2.state}')
    ap3 = CI.simulation_applicability({'layers': {'qb': {}}},
                                      simulation_artifact_declared=False)
    ok(ap3.state == IC.APPLICABLE_AND_CHECKED,
       'a negative declaration CONTRADICTED by draw layers loses -- the '
       'artifact wins over the claim about it')
    ok('artifact contradicts the declaration' in ap3.why,
       'and says so')


def test_applicable_but_unchecked_blocks():
    """RETURN ITEM 4. A governed simulation artifact whose run stored no
    coherence verdict must block, not pass."""
    c = cov(CI.draw_coherence({}, manifest={'layers': {'qb': {}}}),
            CI.C_DRAW_COHERENCE)
    ok(c.applicability == IC.APPLICABLE_BUT_NOT_CHECKED,
       f'the applicability is APPLICABLE_BUT_NOT_CHECKED: {c.applicability}')
    ok(c.state == IC.NOT_CHECKED,
       f'which maps to the blocking coverage state: {c.state}')
    ok('APPLIED AND NOBODY EVALUATED IT' in (c.detail or ''),
       'and says exactly that')
    rep = IC.IntegrityReport(coverage=[c])
    o = GATE.assert_producer_coverage(rep)
    ok(o.state.name == 'FAIL'
       and o.code == GATE.C_INTEGRITY_COVERAGE_MISSING,
       f'and the coverage gate REFUSES: {o.code}')
    ok(GATE.C_DRAW_COHERENCE in str(o.detail),
       'naming the invariant nobody evaluated')


def test_not_applicable_requires_evidence():
    """RETURN ITEM 5. NOT_APPLICABLE is the only state that buys silence, so
    it is the only one that has to prove itself."""
    try:
        IC.inapplicable('there is no simulation here, trust me')
        ok(False, 'an unevidenced NOT_APPLICABLE should be refused')
    except AssertionError as e:
        ok('requires EVIDENCE' in str(e),
           'constructing NOT_APPLICABLE without evidence is refused by name')
    ap = CI.simulation_applicability({'layers': {}},
                                     simulation_artifact_declared=False)
    ok(ap.state == IC.NOT_APPLICABLE and ap.evidence.get(
        'declared_simulation_artifact') is False,
       f'a negative declaration WITH no contradicting layers is '
       f'NOT_APPLICABLE, carrying the declaration as its evidence: '
       f'{ap.evidence}')
    # and the gate refuses a coverage row that claims it unproven
    bare = IC.InvariantCoverage(
        code=GATE.C_DRAW_COHERENCE, owner=IC.OWNER_SIMULATION,
        state=IC.NOT_APPLICABLE, producer='x', producer_version='y',
        detail='nothing to see here')
    o = GATE.assert_producer_coverage(IC.IntegrityReport(coverage=[bare]))
    ok(o.state.name == 'FAIL',
       f'and a coverage row claiming NOT_APPLICABLE with no evidence is '
       f'refused by the gate: {o.code}')
    ok('absent array is not evidence' in o.detail,
       'with the rule stated')
    ok(IC.assert_not_applicable_is_evidenced(
        IC.IntegrityReport(coverage=[bare]), [GATE.C_DRAW_COHERENCE])
       == (GATE.C_DRAW_COHERENCE,),
       'and the unproven code is NAMED, not counted')


def test_every_advertised_producer_evidences_its_not_applicable():
    """The five producers that can report NOT_APPLICABLE all now prove it.
    Retrofitted with the promotion, because the rule is not about one code."""
    from nfl.dfs import eligibility_integrity as EI
    from nfl.production import simulation_integrity as SI
    from nfl.production.state import identity_integrity as II
    from nfl.production.review import provenance_integrity as PI
    for label, rep in (
            ('dfs eligibility', EI.will_not_play_in_dfs_populations()),
            ('missing row ids', SI.missing_row_ids({})),
            ('row mismatch', SI.simulation_row_mismatch({}, {})),
            ('duplicate identity', II.duplicate_player_identity([])),
            ('provenance', PI.unavailable_claimed_as_measured([object()]))):
        c = rep.coverage[0]
        ok(c.state == IC.NOT_APPLICABLE and bool(c.applicability_evidence),
           f'{label}: NOT_APPLICABLE carrying evidence '
           f'{sorted(c.applicability_evidence)}')


# -- 5. the chain -> review bridge -----------------------------------------
def test_the_bridge_transports_the_verdict_with_its_offending_rows():
    chain = {'game_id': 'G1', 'cut': 'CUT1', 'layers': {'allocation': {
        'targets': {'gate': {'code': CI.ALLOC_CONSERVES, 'state': 'PASS'}},
        'carries': {'gate': {'code': CI.ALLOC_FAILS, 'state': 'FAIL',
                             'offending': [{'club': 'SF',
                                            'kind': 'COMPOSITION_NOT_UNIT',
                                            'sum': 0.98}]}}}}}
    with tempfile.TemporaryDirectory() as td:
        w = CB.write(chain, td, slate_key='G1')
        ok(w.state.name == 'PASS' and w.code == CB.CODE_WRITTEN,
           f'the chain verdict is written: {w.code}')
        r = CB.read(td, slate_key='G1')
        ok(r.state.name == 'PASS', f'and read back: {r.code}')
        rep = CI.allocation_conserves(r.value)
        c = cov(rep, CI.C_CONSERVATION)
        ok(c.state == IC.CHECKED_AND_FAILING,
           f'the producer reads the transported verdict to a real finding: '
           f'{c.state}')
        ok(rep.findings[0].subject == 'SF',
           f'with the offending club carried across the bridge intact: '
           f'{rep.findings[0].subject}')
        ok(rep.findings[0].producer_version == CI.SPEC_VERSION
           and rep.findings[0].producer == CI.PRODUCER_CONSERVATION,
           'and the producer and version survive the crossing')


def test_a_bridge_that_fails_its_own_certificate_blocks():
    chain = {'game_id': 'G1', 'layers': {'allocation': {
        'targets': {'gate': {'code': CI.ALLOC_CONSERVES, 'state': 'PASS'}}}}}
    with tempfile.TemporaryDirectory() as td:
        CB.write(chain, td, slate_key='G1')
        p = pathlib.Path(td) / CB.FILENAME
        doc = json.loads(p.read_text())
        doc['rooms']['targets']['code'] = CI.ALLOC_FAILS
        p.write_text(json.dumps(doc))
        r = CB.read(td, slate_key='G1')
        ok(r.state.name == 'FAIL'
           and r.code == CB.CODE_CERTIFICATE_MISMATCH,
           f'editing the verdict without re-certifying is caught: {r.code}')
        ok('come apart' in r.detail,
           'and named as the verdict and its composition having come apart')
        ok(cov(CI.allocation_conserves(None),
               CI.C_CONSERVATION).state == IC.NOT_CHECKED,
           'and a refused bridge means the producer is handed nothing, so '
           'the invariant is NOT_CHECKED -- never a pass')


def test_a_bridge_from_another_slate_certifies_nothing():
    chain = {'game_id': 'G1', 'layers': {'allocation': {
        'targets': {'gate': {'code': CI.ALLOC_CONSERVES, 'state': 'PASS'}}}}}
    with tempfile.TemporaryDirectory() as td:
        CB.write(chain, td, slate_key='G1')
        r = CB.read(td, slate_key='G2')
        ok(r.state.name == 'FAIL' and r.code == CB.CODE_SLATE_MISMATCH,
           f'a verdict about another slate is refused: {r.code}')
    with tempfile.TemporaryDirectory() as td:
        ok(CB.read(td).code == CB.CODE_ABSENT,
           'and an absent bridge is BLOCKED by name, not silently empty')
        ok(CB.write({'layers': {'allocation': {}}}, td).code == CB.CODE_EMPTY,
           'as is a chain result with no club-room verdict to transport')


def test_the_bridge_does_not_duplicate_ownership():
    ok(CB.PRODUCER == 'universe.allocation.assert_allocation_conserves',
       f'the bridge names the ORIGINAL producer as the owner of the '
       f'verdict it carries: {CB.PRODUCER}')
    ok(CB.PRODUCER != CI.PRODUCER_CONSERVATION,
       'which is not the integrity producer -- the bridge transports a '
       'verdict, it does not author one')
    src = pathlib.Path(_REPO / 'nfl/production/universe'
                       / 'conservation_bridge.py').read_text()
    for banned in ('share_renormalised', 'assert_allocation_conserves('):
        ok(banned not in src,
           f'and it recomputes nothing: no {banned!r} in the carrier')


def _run_chain_callers():
    """Files that INVOKE run_chain, found by shape rather than by name.

    This used to grep for the string `run_chain` and drop a hand-written list of
    filenames. That made it wrong in both directions. It counted any module that
    merely NAMES the symbol -- an audit tool enumerating guard call sites does
    exactly that, and `nfl/tools/guard_reachability.py` duly turned this check
    red without a single new caller existing. And the cure would have been worse:
    appending each new filename to the allowlist turns the allowlist into the
    hiding place this repository elsewhere refuses to build
    (`run_suite.tally_tripwires`: "recognised by SHAPE, NOT BY NAME ... so this
    cannot become a hiding place").

    So a `.py` file is a caller only when it contains a CALL whose target
    resolves to the module, alias included. That is strictly stronger for real
    callers, because `import ... as RC; RC.run(...)` is now caught by resolution
    rather than by the literal string happening to appear.

    A `.yml` file is different and keeps the string match: a workflow that names
    the module is invoking it, and there is no call node to find.
    """
    import ast as _a
    hits = []
    for path in sorted((_REPO / 'nfl').rglob('*.py')):
        if path.name in ('run_chain.py', 'conservation_bridge.py',
                         'conservation_integrity.py', 'gate.py'):
            continue
        try:
            src = path.read_text(encoding='utf-8', errors='replace')
        except OSError:
            continue
        if 'run_chain' not in src:
            continue
        try:
            tree = _a.parse(src)
        except SyntaxError:
            continue
        # Every local name that refers to the run_chain module.
        names = {'run_chain'}
        for n in _a.walk(tree):
            if isinstance(n, _a.Import):
                for al in n.names:
                    if al.name.endswith('run_chain'):
                        names.add(al.asname or al.name.split('.')[-1])
            elif isinstance(n, _a.ImportFrom):
                for al in n.names:
                    if al.name == 'run_chain':
                        names.add(al.asname or al.name)
        for n in _a.walk(tree):
            if not isinstance(n, _a.Call):
                continue
            f = n.func
            root = f
            while isinstance(root, _a.Attribute):
                root = root.value
            if isinstance(root, _a.Name) and root.id in names:
                hits.append(f'{path}:{n.lineno}')
                break
    for path in sorted((_REPO / '.github').rglob('*.yml')):
        if 'run_chain' in path.read_text(encoding='utf-8', errors='replace'):
            hits.append(str(path))
    return hits


def test_the_allocation_codes_are_still_relinquished_and_why():
    """The bridge is built and wired. It is not yet production-REACHABLE,
    and the reason is measurable rather than a matter of opinion."""
    callers = _run_chain_callers()
    ok(not callers,
       f'run_chain.run has no orchestrating caller, so nothing places a '
       f'bridge artifact beside a forecast review: {callers}')
    for code in (GATE.C_CONSERVATION, GATE.C_CONSUMER_SCOPE):
        ok(code in GATE.RELINQUISHED_CODES,
           f'{code} therefore stays RELINQUISHED -- advertising it would '
           f'claim a guarantee that depends on a path nothing walks')


def main():
    for t in (test_the_two_allocation_invariants_do_not_share_a_code,
              test_a_scope_failure_is_not_a_conservation_failure,
              test_a_clean_run_passes_both,
              test_no_consuming_set_conserves_but_does_not_establish_scope,
              test_an_unrecognised_allocation_code_is_not_a_pass,
              test_an_impossible_cell_blocks,
              test_a_violation_is_reported_even_without_a_verified_certificate,
              test_a_pass_without_a_verified_certificate_is_not_a_pass,
              test_every_way_of_having_no_verdict_is_not_checked,
              test_it_reads_a_real_sealed_run_status,
              test_the_gate_advertises_only_what_has_a_producer,
              test_the_gate_no_longer_claims_one_code_for_two_invariants,
              test_compose_still_refuses_a_code_claimed_twice,
              test_an_artifact_that_claims_to_be_a_simulation_is_applicable,
              test_applicable_but_unchecked_blocks,
              test_not_applicable_requires_evidence,
              test_every_advertised_producer_evidences_its_not_applicable,
              test_the_bridge_transports_the_verdict_with_its_offending_rows,
              test_a_bridge_that_fails_its_own_certificate_blocks,
              test_a_bridge_from_another_slate_certifies_nothing,
              test_the_bridge_does_not_duplicate_ownership,
              test_the_allocation_codes_are_still_relinquished_and_why):
        print(f'== {t.__name__}')
        t()
    print(f'\nPASSED {PASSED} FAILED {FAILED}')
    return 1 if FAILED else 0


if __name__ == '__main__':
    sys.exit(main())
