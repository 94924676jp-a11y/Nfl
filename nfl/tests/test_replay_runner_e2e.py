"""D23 closes here: the RUNNER, end to end, against a real sealed forecast.

A contract nothing calls is a document. test_replay_contract.py proves the
contract; this proves the thing that actually reproduces a forecast.

THE EIGHT STEPS THE OWNER SPECIFIED

  1. load an existing sealed forecast                          -- section A
  2. replay from its exact partition IDs                       -- section B
  3. prove identical inputs                                    -- section B
  4. prove deterministic rerun                                 -- section C
  5. append a newer lawful historical partition                -- section D
  6. prove ORIGINAL_REPLAY remains unchanged                   -- section D
  7. prove RETROSPECTIVE_RECONSTRUCTION may differ             -- section E
  8. prove the labels cannot be confused                       -- section F

STEP 3 IS CHECKABLE, NOT ASSERTED. Every seal carries `input_bundle_sha256`, a
digest over the content hash of every source consumed. Measured on the
committed 2024_01_ARI_BUF/ARI dry run:

    sealed                               6477fddd245bcc26...
    ORIGINAL_REPLAY from its partitions  6477fddd245bcc26...   identical
    re-selecting at the same clock       6970cb9b6ea65fa8...   different

Both selections are lawful. The second is what the manifest says TODAY, and the
manifest has grown -- which is D23 in one line.

STEP 5 NEEDED NO SEEDING FOR THE REAL CASE: reconciliation with main already
added `official_inactives@fefbd73647bb1e1d`, retrieved 2026-09-12T11:34:53Z,
later than the sealed pick and still inside the 12:00:00Z clock. Section D
ALSO seeds a synthetic one, so the proof does not depend on the corpus staying
in its current state.

Run standalone:  python3.12 nfl/tests/test_replay_runner_e2e.py
"""
import json
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from sportsplatform.governance.outcome import State                # noqa: E402
from nfl.prospective.q9shadow import inputs as IN                  # noqa: E402
from nfl.prospective.q9shadow import replay_runner as RR           # noqa: E402
from nfl.research.shadow import information_set as ISET            # noqa: E402
from nfl.research.shadow import replay_contract as RC              # noqa: E402

PASSED = FAILED = 0
NOT_EXECUTED = []
ROOT = pathlib.Path(__file__).resolve().parents[2]
SEALED = (ROOT / 'nfl' / 'prospective' / 'q9shadow' / 'dryrun'
          / '2024_01_ARI_BUF' / 'ARI' / 'SEALED_FORECAST.json')


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


def not_executed(label, why):
    NOT_EXECUTED.append((label, why))
    print(f'  NOT_EXECUTED {label}  {why}')


def _art():
    return json.loads(SEALED.read_text()) if SEALED.exists() else None


# --------------------------------------------------------------------------
def test_a_step_1_load_a_real_sealed_forecast():
    print('\nA. step 1 -- load a sealed forecast')
    o = RR.load_sealed(SEALED)
    if o.state is not State.PASS:
        not_executed('no sealed forecast', o.code)
        return
    art = o.value
    check('it loads', o.code == 'SEALED_FORECAST_LOADED')
    check('  and records what it consumed',
          len(art['seal']['consumed_partition_ids']) == 7,
          str(len(art['seal']['consumed_partition_ids'])))
    check('  and carries an input bundle digest to check against',
          bool(art.get('input_bundle_sha256')))
    # A forecast that records nothing cannot be replayed, only re-run, and the
    # loader must say which.
    bad = RR.load_sealed(ROOT / 'nfl' / 'tests' / 'no_such_forecast.json')
    check('  a missing artifact refuses by name',
          bad.code == 'SEALED_FORECAST_ABSENT', bad.code)


def test_b_steps_2_and_3_replay_from_recorded_ids_gives_identical_inputs():
    print('\nB. steps 2-3 -- replay from the recorded ids, inputs identical')
    art = _art()
    if art is None:
        not_executed('no sealed forecast', 'nothing to replay')
        return
    o = RR.replay(SEALED, RR.ORIGINAL_REPLAY)
    check('the replay passes', o.state is State.PASS, f'{o.code} {o.detail}')
    check('  with the identity code', o.code == 'REPLAY_INPUTS_IDENTICAL',
          o.code)
    ev = o.evidence
    check('  and it is marked pinned', ev.get('pinned') is True)
    check('  input identity is IDENTICAL',
          ev.get('input_identity') == 'IDENTICAL', str(ev.get('input_identity')))
    check('  and the bundle digest EQUALS the seal\'s own',
          ev['input_bundle_sha256'] == art['input_bundle_sha256'],
          f"{ev['input_bundle_sha256'][:16]} vs "
          f"{art['input_bundle_sha256'][:16]}")
    check('  over exactly the recorded partitions',
          ev['partition_ids'] == sorted(art['seal']['consumed_partition_ids']))


def test_c_step_4_deterministic_rerun():
    print('\nC. step 4 -- a rerun is byte-identical')
    art = _art()
    if art is None:
        not_executed('no sealed forecast', 'nothing to rerun')
        return
    runs = [RR.replay(SEALED, RR.ORIGINAL_REPLAY) for _ in range(3)]
    digs = {r.evidence['input_bundle_sha256'] for r in runs}
    ids = {tuple(r.evidence['partition_ids']) for r in runs}
    check('three runs give one input bundle digest', len(digs) == 1, str(digs))
    check('  and one partition set', len(ids) == 1)
    # The per-source blob digests must agree too, not just the rollup.
    per = [{s: r['blob_sha256'] for s, r in run.value['sources'].items()}
           for run in runs]
    check('  and identical per-source blob digests', per[0] == per[1] == per[2])


def test_d_steps_5_and_6_a_newer_lawful_row_does_not_move_the_replay():
    print('\nD. steps 5-6 -- a newer lawful partition appears; replay unmoved')
    art = _art()
    if art is None:
        not_executed('no sealed forecast', 'nothing to test')
        return
    before = RR.replay(SEALED, RR.ORIGINAL_REPLAY).evidence

    # THE REAL CASE, already in the corpus.
    live = IN.bundle(art['kickoff_utc'], art['written_at'])
    if live.state is State.PASS:
        live_ids = set(RC.partition_ids_of(live.value))
        rec = set(art['seal']['consumed_partition_ids'])
        check('the corpus already holds newer lawful rows for this clock',
              bool(live_ids - rec),
              'if empty, only the synthetic case below is exercised')

    # AND A SYNTHETIC ONE, so the proof does not depend on the corpus state.
    # A fabricated observation is injected into the selector's own view; the
    # MANIFEST IS NOT TOUCHED -- this test writes nothing.
    real_first = ISET.first_observation
    try:
        def seeded():
            obs = dict(real_first())
            src = 'official_inactives'
            newest = max((o for (s, _h), o in obs.items() if s == src),
                         key=lambda o: o['observed_at'], default=None)
            if newest is not None:
                fake = dict(newest)
                fake['sha256'] = 'a' * 64
                fake['observed_at'] = newest['observed_at']
                obs[(src, fake['sha256'])] = fake
            return obs
        ISET.first_observation = seeded
        after = RR.replay(SEALED, RR.ORIGINAL_REPLAY).evidence
    finally:
        ISET.first_observation = real_first

    check('ORIGINAL_REPLAY is unchanged by the newer row',
          after['input_bundle_sha256'] == before['input_bundle_sha256'],
          f"{after['input_bundle_sha256'][:16]} vs "
          f"{before['input_bundle_sha256'][:16]}")
    check('  and still resolves the same partitions',
          after['partition_ids'] == before['partition_ids'])
    check('  and the real selector is restored',
          ISET.first_observation is real_first)


def test_e_step_7_retrospective_may_differ_and_never_claims_identity():
    print('\nE. step 7 -- reconstruction may differ, and labels it honestly')
    art = _art()
    if art is None:
        not_executed('no sealed forecast', 'nothing to reconstruct')
        return
    o = RR.replay(SEALED, RR.RETROSPECTIVE_RECONSTRUCTION)
    check('it passes', o.state is State.PASS, o.code)
    check('  with its own code, not the identity one',
          o.code == 'REPLAY_RECONSTRUCTED', o.code)
    ev = o.evidence
    check('  and is NOT pinned', ev.get('pinned') is False)
    check('  and its identity verdict is never IDENTICAL',
          ev.get('input_identity') in ('DIFFERS', 'AGREES_TODAY'),
          str(ev.get('input_identity')))
    # AGREES_TODAY IS NOT IDENTICAL, and the distinction is the point: agreement
    # is a fact about the corpus right now, not a property of the run.
    check('  and on this corpus it DIFFERS from the seal',
          ev.get('input_identity') == 'DIFFERS',
          f"{ev.get('input_identity')} -- if AGREES_TODAY the manifest has not "
          f"grown and D23's live case is dormant, which is not a pass")


def test_f_step_8_the_labels_cannot_be_confused():
    print('\nF. step 8 -- the modes are not interchangeable')
    art = _art()
    if art is None:
        not_executed('no sealed forecast', 'nothing to confuse')
        return
    o = RR.replay(SEALED, 'REPLAY')
    check('an unknown mode refuses', o.state is State.FAIL
          and o.code == 'REPLAY_MODE_UNKNOWN', o.code)
    import inspect
    sig = inspect.signature(RR.replay)
    check('  and mode is required, with no default',
          sig.parameters['mode'].default is inspect.Parameter.empty)

    a = RR.replay(SEALED, RR.ORIGINAL_REPLAY)
    b = RR.replay(SEALED, RR.RETROSPECTIVE_RECONSTRUCTION)
    check('  the two modes return different codes',
          a.code != b.code, f'{a.code} / {b.code}')
    check('  different pinned flags',
          a.evidence['pinned'] != b.evidence['pinned'])
    check('  and a ledger row records which mode produced it',
          RR.ledger_row(a)['replay_mode'] == RR.ORIGINAL_REPLAY
          and RR.ledger_row(b)['replay_mode']
          == RR.RETROSPECTIVE_RECONSTRUCTION)
    row = RR.ledger_row(a)
    for k in ('game_id', 'replay_mode', 'input_identity',
              'input_bundle_sha256', 'partition_ids', 'rng_seed', 'n_draws'):
        check(f'    ledger row carries {k}', k in row)
    check('    and unsupplied fields stay None rather than being invented',
          row['rng_seed'] is None and row['model_hash'] is None)


def test_g_a_mismatched_bundle_refuses():
    """The check that makes ORIGINAL_REPLAY mean something."""
    print('\nG. a replay that cannot reproduce the seal digest is refused')
    art = _art()
    if art is None:
        not_executed('no sealed forecast', 'nothing to break')
        return
    tampered = json.loads(SEALED.read_text())
    tampered['input_bundle_sha256'] = 'b' * 64
    o = RR.replay(tampered, RR.ORIGINAL_REPLAY)
    check('it refuses by name',
          o.state is State.FAIL and o.code == 'REPLAY_INPUT_BUNDLE_MISMATCH',
          o.code)
    check('  and reports both digests',
          o.evidence.get('sealed') == 'b' * 64
          and o.evidence.get('replayed') == art['input_bundle_sha256'])
    check('  and the sealed file on disk is untouched',
          json.loads(SEALED.read_text())['input_bundle_sha256']
          == art['input_bundle_sha256'])


def test_h_the_runner_writes_nothing():
    print('\nH. the runner is read-only')
    src = (ROOT / 'nfl' / 'prospective' / 'q9shadow'
           / 'replay_runner.py').read_text()
    for forbidden in ('write_text', 'append_seal', "open(", 'mkdir'):
        check(f'  no {forbidden!r}', forbidden not in src,
              'a replay that can write is one bug from rewriting history to '
              'match itself')


if __name__ == '__main__':
    test_a_step_1_load_a_real_sealed_forecast()
    test_b_steps_2_and_3_replay_from_recorded_ids_gives_identical_inputs()
    test_c_step_4_deterministic_rerun()
    test_d_steps_5_and_6_a_newer_lawful_row_does_not_move_the_replay()
    test_e_step_7_retrospective_may_differ_and_never_claims_identity()
    test_f_step_8_the_labels_cannot_be_confused()
    test_g_a_mismatched_bundle_refuses()
    test_h_the_runner_writes_nothing()
    print(f'\n{PASSED} passed, {FAILED} failed, {len(NOT_EXECUTED)} NOT_EXECUTED')
    for label, why in NOT_EXECUTED:
        print(f'  NOT_EXECUTED: {label} -- {why}')
    sys.exit(1 if FAILED else 0)
