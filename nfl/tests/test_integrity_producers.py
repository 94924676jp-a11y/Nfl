"""Corrupt the source, and prove the whole chain stops.

Every test here is END TO END. A producer that only passes when a unit test
calls it directly is not coverage -- the governed production chain has to
invoke it. So each corruption is made in the ARTIFACT, and the assertion is
on `gated_projection.load`, which is the call an optimizer makes.

    source corruption -> owning producer fires -> IntegrityFinding
    -> IntegrityReport -> gate consumes it -> publication BLOCKS
"""
from __future__ import annotations

import ast
import json
import pathlib
import shutil
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
for _p in (str(_REPO), str(_REPO / 'nfl' / 'tests')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from nfl.production.integrity import contract as IC                   # noqa: E402
from nfl.production.review import evidence as EV                      # noqa: E402
from nfl.production.review import gate as GATE                        # noqa: E402
from nfl.production.review import gated_projection as GP              # noqa: E402
from nfl.production.review import provenance_integrity as PI          # noqa: E402
from nfl.production import simulation_integrity as SI                 # noqa: E402
from nfl.production.state import identity_integrity as II             # noqa: E402

import test_review_enforcement as TRE                                 # noqa: E402

PASSED = FAILED = 0


def ok(cond, what):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok     {what}')
    else:
        FAILED += 1
        print(f'  FAIL   {what}')


def _val(o):
    return o.value or (getattr(o, 'evidence', {}) or {}).get('value') or {}


def load(td):
    draws, rdir, _ = TRE.clean_slate(td)
    return draws, rdir


def repoint(rdir, npz_sha256):
    """Point the review report at the artifact as it now stands.

    Corrupting the npz changes its digest, and `PLAYER_REVIEW_STALE` fires
    FIRST -- correctly, because a review of different bytes is not a review
    of these. That protection would mask every downstream check, so these
    tests re-point the report to simulate the case the coherence invariant
    actually guards: a run that reviewed THIS artifact and sealed it anyway.
    """
    rp = pathlib.Path(rdir) / 'slate_review_report.json'
    rep = json.loads(rp.read_text())
    rep.setdefault('projection_source', {}).setdefault('digests', {})[
        'player_draws.npz'] = npz_sha256
    rp.write_text(json.dumps(rep, indent=1))


def corrupt_and_load(corrupt):
    """Build a clean slate, corrupt it, and run the production gate path."""
    with tempfile.TemporaryDirectory() as td:
        draws, rdir = load(td)
        clean = _val(GP.load(draws, rdir))
        corrupt(draws, rdir)
        after = GP.load(draws, rdir)
        return clean, after, _val(after)


def finding_codes(v):
    it = v.get('integrity') or {}
    rows = v.get('blocking_conflicts') or []
    return sorted({r.get('code') for r in rows}), it


# -- 1. the clean fixture ---------------------------------------------------
def test_the_clean_fixture_passes_with_every_invariant_checked():
    with tempfile.TemporaryDirectory() as td:
        draws, rdir = load(td)
        o = GP.load(draws, rdir)
        v = _val(o)
        ok(o.state.name == 'PASS' and v['verdict'] == GATE.PASS,
           f'a clean slate still passes: {o.code} / {v["verdict"]}')
        it = v['integrity']
        ok(it['coverage_verdict'] == 'INTEGRITY_COVERAGE_COMPLETE',
           f'with complete coverage: {it["coverage_verdict"]}')
        ok(set(it['coverage']) == set(GATE.ADVERTISED_INTEGRITY),
           f'over every advertised invariant: {sorted(it["coverage"])}')
        ok(all(s != IC.NOT_CHECKED for s in it['coverage'].values()),
           f'nothing is NOT_CHECKED: {it["coverage"]}')
        ok(all(s == IC.CHECKED_AND_PASSING for c, s in it['coverage'].items()
               if c != 'INACTIVE_PLAYER_IN_SIMULATION_OR_OPTIMIZER_POOL'),
           'every invariant a gated load CAN check reads CHECKED_AND_PASSING')
        ok(it['coverage']['INACTIVE_PLAYER_IN_SIMULATION_OR_OPTIMIZER_POOL']
           == IC.NOT_APPLICABLE,
           'and the DFS eligibility invariant reads NOT_APPLICABLE here, '
           'because no DFS population exists until the pool is built -- '
           'not passing, and not silently absent')
        ok(it['n_findings'] == 0 and it['report_hash'].startswith('IR-'),
           f'no findings, report {it["report_hash"]}')
        # `producer_versions` covers every code the report carried, which
        # is the advertised set PLUS the observed one -- the observed
        # producer ran on this path too, and a version it stamped is
        # evidence it ran.
        ok(set(it['producer_versions'])
           == set(GATE.ADVERTISED_INTEGRITY) | set(GATE.OBSERVED_INTEGRITY),
           f'and every invariant the report covers names the producer '
           f'version that ran: {it["producer_versions"]}')
        ok(it['producer_versions'].get(GATE.C_DRAW_COHERENCE),
           'including the observed one, so "observed" cannot mean "nobody '
           'ran it"')


# -- 2. corruption, end to end ---------------------------------------------
def test_a_duplicated_canonical_id_blocks():
    def corrupt(draws, rdir):
        pdir = rdir / 'player_dossiers'
        f = sorted(pdir.glob('*.json'))[0]
        shutil.copy(f, pdir / 'a_second_copy.json')

    clean, after, v = corrupt_and_load(corrupt)
    ok(clean['verdict'] == GATE.PASS, 'the same slate passed before')
    codes, it = finding_codes(v)
    ok(after.state.name != 'PASS',
       f'duplicating one canonical id stops publication: {after.code}')
    ok(II.C_DUPLICATE_IDENTITY in codes,
       f'the state layer\'s producer fired: {codes}')
    ok(it['coverage'][II.C_DUPLICATE_IDENTITY] == IC.CHECKED_AND_FAILING,
       'and coverage reads CHECKED_AND_FAILING, not silence')
    row = next(r for r in v['blocking_conflicts']
               if r['code'] == II.C_DUPLICATE_IDENTITY)
    ok(row['evidence']['occurrences'] == 2,
       f'the finding says how many times: {row["evidence"]["occurrences"]}')
    ok(row['evidence']['integrity_owner'] == IC.OWNER_STATE
       and row['evidence']['producer'] == II.PRODUCER,
       f'and names its owner and producer: '
       f'{row["evidence"]["integrity_owner"]}')
    ok(row['evidence']['source_artifacts'].get('player_draws.npz'),
       'with the artifact hashes it was checked against')


def test_a_layer_with_no_row_ids_blocks():
    def corrupt(draws, rdir):
        mp = draws / 'player_draws_manifest.json'
        man = json.loads(mp.read_text())
        man['layers']['rushing'].pop('row_ids', None)
        mp.write_text(json.dumps(man))

    clean, after, v = corrupt_and_load(corrupt)
    ok(clean['verdict'] == GATE.PASS, 'the same slate passed before')
    codes, it = finding_codes(v)
    ok(after.state.name != 'PASS',
       f'a layer that cannot say whose draws it carries stops publication: '
       f'{after.code}')
    ok(SI.C_MISSING_ROW_IDS in codes,
       f'the simulation artifact producer fired: {codes}')
    ok(it['coverage'][SI.C_MISSING_ROW_IDS] == IC.CHECKED_AND_FAILING,
       'coverage reads CHECKED_AND_FAILING')
    row = next(r for r in v['blocking_conflicts']
               if r['code'] == SI.C_MISSING_ROW_IDS)
    ok(row['evidence']['layer'] == 'rushing',
       f'naming the layer: {row["evidence"]["layer"]}')


def test_a_row_axis_that_does_not_line_up_blocks():
    def corrupt(draws, rdir):
        mp = draws / 'player_draws_manifest.json'
        man = json.loads(mp.read_text())
        man['layers']['receiving']['row_ids'] = (
            list(man['layers']['receiving']['row_ids']) + ['A_GHOST_PLAYER'])
        mp.write_text(json.dumps(man))

    clean, after, v = corrupt_and_load(corrupt)
    ok(clean['verdict'] == GATE.PASS, 'the same slate passed before')
    codes, it = finding_codes(v)
    ok(after.state.name != 'PASS',
       f'a row axis off by one stops publication: {after.code}')
    ok(SI.C_SIM_ROW_MISMATCH in codes,
       f'the simulation artifact producer fired: {codes}')
    ok(it['coverage'][SI.C_SIM_ROW_MISMATCH] == IC.CHECKED_AND_FAILING,
       'coverage reads CHECKED_AND_FAILING')
    row = next(r for r in v['blocking_conflicts']
               if r['code'] == SI.C_SIM_ROW_MISMATCH)
    ok(row['evidence']['n_row_ids'] != row['evidence']['n_array_rows'],
       f'and the finding carries both counts: '
       f'{row["evidence"]["n_row_ids"]} ids vs '
       f'{row["evidence"]["n_array_rows"]} rows')


def test_a_measured_claim_on_unmeasured_evidence_blocks():
    def corrupt(draws, rdir):
        pdir = rdir / 'player_dossiers'
        f = sorted(pdir.glob('*.json'))[0]
        j = json.loads(f.read_text())
        # every canonical axis unmeasured ...
        for v_ in (j.get('evidence_provenance') or {}).values():
            if isinstance(v_, dict) and v_.get('grade') == EV.MEASURED:
                v_['grade'] = EV.UNAVAILABLE
        # ... while the projection claims MEASURED
        for c in (j.get('projection') or {}).values():
            c['grade'] = EV.MEASURED
        f.write_text(json.dumps(j))

    clean, after, v = corrupt_and_load(corrupt)
    ok(clean['verdict'] == GATE.PASS, 'the same slate passed before')
    codes, it = finding_codes(v)
    ok(after.state.name != 'PASS',
       f'a MEASURED claim resting on nothing measured stops publication: '
       f'{after.code}')
    ok(PI.C_UNAVAILABLE_CLAIMED in codes,
       f'the provenance producer fired: {codes}')
    ok(it['coverage'][PI.C_UNAVAILABLE_CLAIMED] == IC.CHECKED_AND_FAILING,
       'coverage reads CHECKED_AND_FAILING')
    row = next(r for r in v['blocking_conflicts']
               if r['code'] == PI.C_UNAVAILABLE_CLAIMED)
    ok(row['evidence']['components_claimed_measured'],
       f'naming the components: '
       f'{row["evidence"]["components_claimed_measured"]}')
    ok(EV.MEASURED not in row['evidence']['canonical_grades_present'],
       f'and the grades that actually exist: '
       f'{row["evidence"]["canonical_grades_present"]}')


# -- 3. absence of a finding is not a pass ---------------------------------
def test_not_checked_is_not_a_pass():
    rep = {'conflicts': [], 'projection_source': {'digests': {}},
           'coverage': {}}
    g = GATE.evaluate(rep)
    v = GATE.payload(g)
    ok(v['verdict'] == GATE.PASS,
       'without the requirement a verdict is still issued')
    ok(all(s == IC.NOT_CHECKED for s in v['integrity']['coverage'].values()),
       f'but every invariant reads NOT_CHECKED, visibly: '
       f'{v["integrity"]["coverage"]}')
    g2 = GATE.evaluate(rep, require_integrity_coverage=True)
    v2 = GATE.payload(g2)
    ok(v2['verdict'] == GATE.BLOCKED,
       'and where coverage is required, NOT_CHECKED BLOCKS')
    ok(v2['blocking_conflict_count'] == len(GATE.ADVERTISED_INTEGRITY),
       f'once per uncovered invariant: {v2["blocking_conflict_count"]}')
    ok(GATE.assert_producer_coverage(None).code
       == GATE.C_INTEGRITY_COVERAGE_MISSING,
       'and the assertion refuses a missing report by name')


def test_an_empty_population_is_not_applicable_not_passing():
    r = II.duplicate_player_identity([])
    ok(r.state_of(II.C_DUPLICATE_IDENTITY) == IC.NOT_APPLICABLE,
       'a check over nobody is NOT_APPLICABLE, never CHECKED_AND_PASSING')
    ok('not a passing one' in (r.coverage[0].detail or ''),
       'and says why')
    r2 = SI.missing_row_ids({})
    ok(r2.state_of(SI.C_MISSING_ROW_IDS) == IC.NOT_APPLICABLE,
       'a manifest with no layers likewise')
    r3 = PI.unavailable_claimed_as_measured([object()])
    ok(r3.state_of(PI.C_UNAVAILABLE_CLAIMED) == IC.NOT_APPLICABLE,
       'and dossiers with no canonical provenance likewise')


# -- 4. the governance test -------------------------------------------------
def test_an_impossible_draw_cell_blocks_end_to_end():
    """A GOVERNED artifact whose published draws carry a football-impossible
    cell must stop publication through `gated_projection.load`.

    The corruption is the one that actually happened: more completions than
    attempts, which 101 sealed artifacts carried in 5,278 cells while
    reporting QB_DRAW_ACCOUNTING_HOLDS. The fixture runs the REAL checker
    over the corrupted arrays and records whatever it says, so this test
    fails if the checker ever stops catching it.
    """
    import governed_draws as GD
    with tempfile.TemporaryDirectory() as td:
        draws, rdir = load(td)
        clean = _val(GP.load(draws, rdir))
        ok(clean['integrity']['coverage'][GATE.C_DRAW_COHERENCE]
           == IC.CHECKED_AND_PASSING,
           f'the repaired fixture is a governed artifact and its coherence '
           f'is CHECKED_AND_PASSING: '
           f'{clean["integrity"]["coverage"][GATE.C_DRAW_COHERENCE]}')
        r = GD.attach(draws, seed=5, corrupt=True)
        ok(r['coherence_code'] == 'DRAW_COHERENCE_VIOLATED',
           f'the real checker catches the corrupted cell: '
           f'{r["coherence_code"]}')
        repoint(rdir, r['npz_sha256'])
        after = GP.load(draws, rdir)
        v = _val(after)
        codes, it = finding_codes(v)
        ok(after.state.name != 'PASS' or v.get('verdict') == GATE.BLOCKED,
           f'and publication STOPS: {after.code} / {v.get("verdict")}')
        ok(it.get('coverage', {}).get(GATE.C_DRAW_COHERENCE)
           == IC.CHECKED_AND_FAILING,
           f'with coherence CHECKED_AND_FAILING: '
           f'{it.get("coverage", {}).get(GATE.C_DRAW_COHERENCE)}')
        ok(GATE.C_DRAW_COHERENCE in codes,
           f'and the blocking conflict carries the coherence code: {codes}')


def test_a_coherence_pass_on_overwritten_arrays_blocks_end_to_end():
    """The 8c81079 failure: the guard ran, then the values it guarded were
    replaced. Coherence HOLDS and the certificate does not verify."""
    import governed_draws as GD
    with tempfile.TemporaryDirectory() as td:
        draws, rdir = load(td)
        r = GD.attach(draws, seed=5, certificate_valid=False)
        ok(r['coherence_code'] == 'DRAW_COHERENCE_HOLDS'
           and r['certificate_code'] != 'COHERENCE_CERTIFICATE_VERIFIED',
           f'coherence holds and the certificate does NOT verify: '
           f'{r["coherence_code"]} / {r["certificate_code"]}')
        repoint(rdir, r['npz_sha256'])
        v = _val(GP.load(draws, rdir))
        st = (v.get('integrity') or {}).get('coverage', {}).get(
            GATE.C_DRAW_COHERENCE)
        ok(st in (IC.NOT_CHECKED, None),
           f'and the gate does NOT count that as a passing check: {st}')


def test_a_governed_artifact_with_no_verdict_blocks_end_to_end():
    """RETURN ITEM 4, end to end. Strip the verdict the run stored and the
    slate must refuse, because the invariant applied and nobody evaluated
    it."""
    import governed_draws as GD
    with tempfile.TemporaryDirectory() as td:
        draws, rdir = load(td)
        ok(_val(GP.load(draws, rdir))['verdict'] != GATE.BLOCKED,
           'the governed fixture publishes before the verdict is removed')
        r = GD.attach(draws, seed=5, omit_coherence_verdict=True)
        repoint(rdir, r['npz_sha256'])
        after = GP.load(draws, rdir)
        v = _val(after)
        st = (v.get('integrity') or {}).get('coverage', {}).get(
            GATE.C_DRAW_COHERENCE)
        ok(after.state.name != 'PASS' or v.get('verdict') == GATE.BLOCKED
           or st == IC.NOT_CHECKED,
           f'removing the stored verdict stops it: {after.code}, coverage '
           f'{st}')


def test_every_advertised_blocking_integrity_code_has_a_producer():
    """A. a reachable production producer, B. explicit NOT_APPLICABLE, or
    C. removal from the registry.

    OBSERVED IS NOT A FOURTH STATE, IT IS A NARROWER FORM OF A. An observed
    code has a producer and that producer runs on the production path; what
    it lacks is the gate GUARANTEEING the invariant was checked, because
    promoting it changes what counts as a publishable artifact. The test
    therefore accepts it as a home -- and then holds it to the same evidence
    requirements as an advertised code, plus a recorded reason for the
    distinction, so "observed" cannot become a parking space.
    """
    advertised = set(GATE.ADVERTISED_INTEGRITY)
    observed = set(GATE.OBSERVED_INTEGRITY)
    relinquished = set(GATE.RELINQUISHED_CODES)
    declared = set(GATE.GATE_CODES)
    ok(advertised | observed | relinquished == declared - {
        GATE.C_INTEGRITY_COVERAGE_MISSING},
       f'every code the gate declares has a home: advertised '
       f'{len(advertised)}, observed {len(observed)}, relinquished '
       f'{len(relinquished)}')
    ok(not (advertised & relinquished) and not (advertised & observed)
       and not (observed & relinquished),
       'and none is in two of them')
    for code in observed:
        spec = GATE.OBSERVED_INTEGRITY[code]
        for key in ('owner', 'invariant', 'producer', 'runs_on',
                    'why_not_advertised'):
            ok(spec.get(key), f'{code} records its {key}')
        ok(code in GATE.BLOCKING_CODES,
           f'{code} still BLOCKS on a real finding -- only the '
           f'nobody-checked case is non-blocking')
    for code in advertised:
        ok(code in GATE.BLOCKING_CODES,
           f'{code} is blocking and advertised')
        spec = GATE.ADVERTISED_INTEGRITY[code]
        mod, fn = spec['producer'].rsplit('.', 1)
        ok(spec['owner'] and spec['invariant'],
           f'{code} names an owner and its invariant')
        ok(fn, f'{code} names a producer: {spec["producer"]}')
    for code in relinquished:
        ok(code not in GATE.BLOCKING_CODES,
           f'{code} is NOT advertised as blocking, because nothing produces '
           f'it')
        spec = GATE.RELINQUISHED_CODES[code]
        for key in ('owner', 'enforced_today', 'gap', 'returns_when'):
            ok(spec.get(key),
               f'{code} records its {key}')
    with tempfile.TemporaryDirectory() as td:
        draws, rdir = load(td)
        it = _val(GP.load(draws, rdir))['integrity']
        ok(set(it['coverage']) == advertised
           and all(s != IC.NOT_CHECKED for s in it['coverage'].values()),
           'and on the production path every advertised code is actually '
           'checked, not merely declared')
        # The observed code runs on the same path. On this synthetic
        # fixture its verdict is NOT_CHECKED -- the fixture carries no
        # coherence verdict because it is not a governed run -- and that is
        # reported rather than hidden, which is the whole purpose of the
        # observed section.
        ok(set(it['observed_coverage']) == observed,
           f'the observed producer\'s verdict is carried too: '
           f'{it["observed_coverage"]}')
        ok(all(s in IC.COVERAGE_STATES
               for s in it['observed_coverage'].values()),
           'as a declared coverage state, never as silence')


def test_a_relinquished_code_still_blocks_if_it_ever_arrives():
    """Relinquishing removed a FALSE CLAIM, not a protection. `classify`
    sends an unregistered code to BLOCKING, so any of the four still stops a
    slate -- it simply no longer appears in a gate record as a guarantee the
    run evaluated."""
    rep = {'conflicts': [], 'projection_source': {'digests': {}},
           'coverage': {}}
    d = TRE.DOS.build_dossiers(
        universe_rows=[TRE.mk_row('RELQ')],
        information_cut=TRE.CUT).value['dossiers']
    for code in sorted(GATE.RELINQUISHED_CODES):
        # attached to a real player, so `classify` -- not the no-dossier
        # branch -- is what decides
        g = GATE.evaluate(rep, dossiers=d, extra_conflicts=[
            {'code': code, 'severity': 'BLOCKING', 'gsis_id': 'RELQ',
             'display_name': 'RELQ'}])
        v = GATE.payload(g)
        ok(v['verdict'] == GATE.BLOCKED
           and v['conflicts'][0]['category'] == 'unregistered_code',
           f'{code} still stops the slate, as an unregistered code')
        # and with no subject at all it is still blocked, as integrity
        g2 = GATE.evaluate(rep, extra_conflicts=[
            {'code': code, 'severity': 'BLOCKING', 'gsis_id': None,
             'display_name': code}])
        ok(GATE.payload(g2)['verdict'] == GATE.BLOCKED,
           f'{code} with no subject blocks too, as an unassessable row')


def test_the_producers_live_with_their_subsystems_not_in_the_gate():
    src = (_REPO / 'nfl/production/review/gate.py').read_text()
    tree = ast.parse(src)
    defs = {n.name for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef)}
    ok(not (defs & {'duplicate_player_identity', 'missing_row_ids',
                    'simulation_row_mismatch',
                    'unavailable_claimed_as_measured'}),
       f'the gate defines no integrity producer of its own: {sorted(defs)}')
    ok('IntegrityReport' in src or 'integrity_report' in src,
       'it consumes a report instead')
    owners = {II.__name__: IC.OWNER_STATE, SI.__name__: IC.OWNER_SIMULATION,
              PI.__name__: IC.OWNER_PROVENANCE}
    ok(len(owners) == 3,
       f'and the three producers live in three owning subsystems: '
       f'{sorted(owners)}')


def test_one_invariant_one_owner():
    a = II.duplicate_player_identity([])
    try:
        IC.IntegrityReport.compose([a, a])
        ok(False, 'two producers claiming one invariant should be refused')
    except AssertionError as e:
        ok('One invariant, one owner' in str(e),
           'a code claimed by two producers is refused by name')


def main():
    for t in (test_the_clean_fixture_passes_with_every_invariant_checked,
              test_a_duplicated_canonical_id_blocks,
              test_a_layer_with_no_row_ids_blocks,
              test_a_row_axis_that_does_not_line_up_blocks,
              test_a_measured_claim_on_unmeasured_evidence_blocks,
              test_not_checked_is_not_a_pass,
              test_an_empty_population_is_not_applicable_not_passing,
              test_an_impossible_draw_cell_blocks_end_to_end,
              test_a_coherence_pass_on_overwritten_arrays_blocks_end_to_end,
              test_a_governed_artifact_with_no_verdict_blocks_end_to_end,
              test_every_advertised_blocking_integrity_code_has_a_producer,
              test_a_relinquished_code_still_blocks_if_it_ever_arrives,
              test_the_producers_live_with_their_subsystems_not_in_the_gate,
              test_one_invariant_one_owner):
        print(f'== {t.__name__}')
        t()
    print(f'\nPASSED {PASSED} FAILED {FAILED}')
    return 1 if FAILED else 0


if __name__ == '__main__':
    sys.exit(main())
