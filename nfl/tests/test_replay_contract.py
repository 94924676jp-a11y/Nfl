"""D23's six-step proof: the same clock, a grown manifest, two honest answers.

THE PROOF THE OWNER SPECIFIED, and every step is run against the real sealed
artifact and the real manifest rather than a fixture:

  1. a forecast is sealed                     -- taken from the committed dry run
  2. its consumed partitions are recorded     -- 7 of them, read from the seal
  3. the manifest ACQUIRES a newer row that   -- already true: reconciliation
     would also have been lawful at the          with main added exactly such
     original clock                              rows, which is what caused D23
  4. ORIGINAL_REPLAY is unchanged             -- section C
  5. RETROSPECTIVE_RECONSTRUCTION may consume -- section D
     the broader lawful set
  6. the two are never confused               -- sections E and F

Step 3 needed no seeding. `2024_01_ARI_BUF` at written_at 2026-09-12T12:00:00Z
sealed `official_inactives@67511bb2cfc1e9f3`, retrieved 2026-09-11T00:44:00Z.
The manifest now also holds `official_inactives@fefbd73647bb1e1d`, retrieved
2026-09-12T11:34:53Z -- later, still before the clock, and absent from this
branch at the time of sealing (0 rows at 382556b, 0 at the common ancestor, 3
on main). The world performed the experiment; this file measures it.

Run standalone:  python3.12 nfl/tests/test_replay_contract.py
"""
import json
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from nfl.research.shadow import information_set as ISET                # noqa: E402
from nfl.research.shadow import replay_contract as RC                  # noqa: E402

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


def _sealed():
    if not SEALED.exists():
        return None
    return json.loads(SEALED.read_text())


# --------------------------------------------------------------------------
def test_a_the_modes_are_named_and_a_default_is_impossible():
    print('\nA. three modes, no default')
    check('the three modes are declared',
          set(RC.MODES) == {'ORIGINAL_REPLAY', 'RETROSPECTIVE_RECONSTRUCTION',
                            'NEW_CANDIDATE_BACKTEST'}, str(RC.MODES))
    check('ORIGINAL_REPLAY is the pinned one',
          RC.PINNED_MODES == (RC.ORIGINAL_REPLAY,), str(RC.PINNED_MODES))
    try:
        RC.build_for_mode('REPLAY', kickoff_utc='2026-01-01T00:00:00Z')
        check('an unknown mode refuses', False, 'it returned')
    except RC.ReplayRefusal as e:
        check('an unknown mode refuses by name',
              e.code == 'REPLAY_MODE_UNKNOWN', e.code)
    # A MODE CANNOT BE OMITTED. There is no default, because a default would be
    # chosen wrongly exactly once and inherited everywhere after that.
    import inspect
    sig = inspect.signature(RC.build_for_mode)
    check('  and mode is a required positional parameter',
          sig.parameters['mode'].default is inspect.Parameter.empty)


def test_b_step_3_the_manifest_really_did_grow_past_the_seal():
    """No seeding needed -- reconciliation with main performed step 3."""
    print('\nB. step 3: a newer row that was also lawful at the same clock')
    art = _sealed()
    if art is None:
        not_executed('no sealed dry run on disk', 'nothing to prove against')
        return
    written_at = art['written_at']
    recorded = art['seal']['consumed_partition_ids']
    check('the seal records its consumed partitions',
          len(recorded) == 7, f'{len(recorded)}')

    live = ISET.build(art['kickoff_utc'], observed_before=written_at)
    live_ids = RC.partition_ids_of(live)
    drift = sorted(set(recorded) ^ set(live_ids))
    check('re-running selection at the SAME clock now yields a different set',
          bool(drift),
          'if this is empty the manifest has not grown since the seal and the '
          'experiment is not live -- re-measure, do not delete')
    print(f'       recorded {len(recorded)}, re-selected {len(live_ids)}, '
          f'{len(drift)} differing:')
    for d in drift[:10]:
        print(f'         {d}')


def test_c_step_4_original_replay_is_unchanged():
    print('\nC. step 4: ORIGINAL_REPLAY consumes exactly what was recorded')
    art = _sealed()
    if art is None:
        not_executed('no sealed dry run', 'nothing to replay')
        return
    recorded = art['seal']['consumed_partition_ids']
    iset = RC.build_for_mode(RC.ORIGINAL_REPLAY,
                             kickoff_utc=art['kickoff_utc'],
                             consumed_partition_ids=recorded)
    got = RC.partition_ids_of(iset)
    check('the replayed input set equals the recorded one, exactly',
          got == sorted(recorded), f'{got} vs {sorted(recorded)}')
    check('  and it is marked pinned', iset.get('pinned') is True)
    check('  and every partition names what pinned it',
          all(r.get('pinned_by') == 'consumed_partition_ids'
              for r in iset['sources'].values()))
    # DETERMINISM: the same call twice is the same answer.
    again = RC.build_for_mode(RC.ORIGINAL_REPLAY,
                              kickoff_utc=art['kickoff_utc'],
                              consumed_partition_ids=recorded)
    check('  and a second identical call gives an identical set',
          RC.partition_ids_of(again) == got)


def test_d_step_5_retrospective_may_consume_the_broader_set():
    print('\nD. step 5: RETROSPECTIVE_RECONSTRUCTION re-selects, and says so')
    art = _sealed()
    if art is None:
        not_executed('no sealed dry run', 'nothing to reconstruct')
        return
    iset = RC.build_for_mode(RC.RETROSPECTIVE_RECONSTRUCTION,
                             kickoff_utc=art['kickoff_utc'],
                             written_at=art['written_at'])
    check('it is NOT marked pinned', iset.get('pinned') is False)
    check('  and it carries its mode in the descriptor',
          iset.get('mode') == RC.RETROSPECTIVE_RECONSTRUCTION)
    recorded = sorted(art['seal']['consumed_partition_ids'])
    check('  and it is allowed to differ from the original',
          RC.partition_ids_of(iset) != recorded,
          'identical here only means the manifest has not grown')


def test_e_step_6_the_two_are_never_confused():
    print('\nE. step 6: the modes cannot be used interchangeably')
    art = _sealed()
    if art is None:
        not_executed('no sealed dry run', 'nothing to compare')
        return
    try:
        RC.build_for_mode(RC.ORIGINAL_REPLAY,
                          kickoff_utc=art['kickoff_utc'],
                          written_at=art['written_at'])
        check('ORIGINAL_REPLAY given only a clock refuses', False,
              'it re-selected, which is the defect')
    except RC.ReplayRefusal as e:
        check('ORIGINAL_REPLAY given only a clock REFUSES by name',
              e.code == 'PINNED_MODE_WITHOUT_RECORDED_PARTITIONS', e.code)
    try:
        RC.build_for_mode(RC.RETROSPECTIVE_RECONSTRUCTION,
                          kickoff_utc=art['kickoff_utc'])
        check('an unpinned mode without a clock refuses', False, 'it returned')
    except RC.ReplayRefusal as e:
        check('  and an unpinned mode without a clock refuses too',
              e.code == 'UNPINNED_MODE_WITHOUT_CLOCK', e.code)


def test_f_a_missing_partition_refuses_and_never_substitutes():
    """The rule that makes the whole contract worth having."""
    print('\nF. a missing original partition REFUSES, never substitutes')
    art = _sealed()
    if art is None:
        not_executed('no sealed dry run', 'nothing to break')
        return
    recorded = list(art['seal']['consumed_partition_ids'])
    # Replace one real address with one that cannot resolve. The nearest lawful
    # blob for that source EXISTS -- substituting it is exactly the temptation.
    broken = [p if not p.startswith('official_inactives@')
              else 'official_inactives@' + ('0' * 16) for p in recorded]
    check('the seeded set still names every source',
          len(broken) == len(recorded))
    try:
        RC.build_from_partition_ids(broken, art['kickoff_utc'])
        check('an unresolvable partition refuses', False,
              'it returned a set, which means it substituted')
    except RC.ReplayRefusal as e:
        check('an unresolvable partition REFUSES by name',
              e.code == 'ORIGINAL_PARTITION_UNAVAILABLE', e.code)
        check('  and names which partition and why',
              bool(e.evidence.get('missing'))
              and 'NOT_IN_MANIFEST' in str(e.evidence['missing']),
              str(e.evidence)[:180])
    # And the malformed case is a different, separately named refusal.
    try:
        RC.build_from_partition_ids(['not-a-partition-id'],
                                    art['kickoff_utc'])
        check('a malformed id refuses', False, 'it returned')
    except RC.ReplayRefusal as e:
        check('  a malformed id is a DIFFERENT named refusal',
              e.code == 'PARTITION_ID_MALFORMED', e.code)
    try:
        RC.build_from_partition_ids([], art['kickoff_utc'])
        check('an empty recorded set refuses', False, 'it returned')
    except RC.ReplayRefusal as e:
        check('  an empty recorded set is a third named refusal',
              e.code == 'NO_RECORDED_PARTITIONS', e.code)


def test_g_no_seal_was_touched():
    """The contract reads seals. It must never write one."""
    print('\nG. nothing here writes a seal')
    src = (ROOT / 'nfl' / 'research' / 'shadow'
           / 'replay_contract.py').read_text()
    for forbidden in ('write_text', 'open(', 'append_seal', 'w+', "'w'"):
        check(f'  replay_contract does not {forbidden!r}',
              forbidden not in src,
              'a module that can rewrite a seal while reading it is one bug '
              'away from rewriting history to match a replay')


if __name__ == '__main__':
    test_a_the_modes_are_named_and_a_default_is_impossible()
    test_b_step_3_the_manifest_really_did_grow_past_the_seal()
    test_c_step_4_original_replay_is_unchanged()
    test_d_step_5_retrospective_may_consume_the_broader_set()
    test_e_step_6_the_two_are_never_confused()
    test_f_a_missing_partition_refuses_and_never_substitutes()
    test_g_no_seal_was_touched()
    print(f'\n{PASSED} passed, {FAILED} failed, {len(NOT_EXECUTED)} NOT_EXECUTED')
    for label, why in NOT_EXECUTED:
        print(f'  NOT_EXECUTED: {label} -- {why}')
    sys.exit(1 if FAILED else 0)
