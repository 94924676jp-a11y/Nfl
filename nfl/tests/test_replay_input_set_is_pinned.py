"""ENG-001. The replay's input set is a function of the seal, and of nothing else.

`test_replay_contract.py` proves the three modes are distinct and that a
missing partition refuses. `test_replay_runner_e2e.py` proves a real sealed
forecast reproduces its own input digest. This file covers the three
acceptance conditions neither of them reaches, and each one is here because
the property it checks would otherwise hold only BY CONSTRUCTION -- which is
another way of saying nobody measured it.

WHAT IS ACTUALLY AT RISK

The manifest in this checkout holds THIRTEEN sources. The 2024_01_ARI_BUF seal
recorded SEVEN. The six it never recorded are:

    dk_entries  dk_salaries  dk_salaries_early
    hardrock_market_snapshot  official_status_evidence  pbp

Two of those are things the owner has ruled may never reach a football
forecast: `pbp` is realised play-by-play of the game being forecast, and
`hardrock_market_snapshot` is sportsbook price. They are in the manifest
because later work captured them, and they are dated whenever they were
captured. A replay that re-selected against today's manifest is a replay
whose source LIST, not merely whose vintage, could grow.

Today two independent things stop that, and it matters which is which:

  1. `information_set.build` selects from a declared source list, so a source
     absent from that list is never picked -- and that guard has nothing to do
     with replay. It protects a NEW FORECAST.
  2. `build_from_partition_ids` iterates the RECORDED IDS and nothing else, so
     the source list of a replay is fixed by the seal.

Guard 1 could be relaxed tomorrow by someone adding a source, entirely
legitimately, and guard 2 would still hold. Section B proves guard 2 standing
on its own, with guard 1 removed from the picture -- because a test that only
passes while a second, unrelated mechanism happens to agree with it is not
testing what it says it is.

Run standalone:  python3.12 nfl/tests/test_replay_input_set_is_pinned.py
"""
import inspect
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

#: A source name that is deliberately not in the manifest, not in the seal and
#: not in any declared source list. If it ever appears in a replay, the replay
#: read something other than the seal.
INTRUDER = 'source_added_after_the_historical_run'


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


def _recorded(art):
    return sorted(art['seal']['consumed_partition_ids'])


# --------------------------------------------------------------------------
def test_a_the_pinned_path_cannot_reach_the_selector_at_all():
    """Acceptance 6, structurally. Selection logic cannot move a replay.

    The behavioural version of this -- monkeypatch the selector, show the
    replay unmoved -- is in the e2e file. This is the stronger statement and
    the cheaper one: the pinned path does not CALL the selector, so there is
    no version of `build` that could change the answer.
    """
    print('\nA. acceptance 6 -- the pinned path never calls the selector')
    src = inspect.getsource(RC.build_from_partition_ids)
    check('build_from_partition_ids does not call ISET.build',
          'ISET.build(' not in src and '.build(' not in src,
          'it reaches the clock-bounded selector, so selection logic can '
          'move a replay')
    check('  and does not take a clock to select against',
          'observed_before' not in src,
          'a pinned rebuild has no use for a cutoff')
    # It resolves addresses, which is a lookup, not a selection.
    for needed in ('first_observation', 'blob_for'):
        check(f'  it resolves addresses via ISET.{needed}',
              f'{needed}(' in src)

    # AND THE SAME QUESTION OF THE RUNNER, which is what callers use.
    rsrc = inspect.getsource(RR.replay)
    pinned_block = rsrc.split('# ---- the unpinned modes')[0]
    check('the runner\'s ORIGINAL_REPLAY branch calls only the pinned builder',
          'bundle_from_partition_ids' in pinned_block
          and 'IN.bundle(' not in pinned_block,
          'the pinned branch reaches the re-selecting bundle()')


def test_b_a_source_added_later_cannot_enter_a_replay():
    """Acceptance 5, with the OTHER guard deliberately taken out of the way.

    The seal's source list is fixed by the seal. To show that standing alone,
    an entirely new source is injected into the manifest VIEW -- resolvable,
    on disk, lawful-looking -- and the replay is asked again. The manifest
    file is not touched; this test writes nothing.

    The second half is the part that makes the first half mean anything: the
    same injected source IS resolvable when it is named in the recorded ids.
    Without that, a pass would be indistinguishable from an injection that
    silently did nothing -- which is exactly how four classifications in this
    project went wrong.
    """
    print('\nB. acceptance 5 -- a later source cannot enter, guard 1 removed')
    art = _art()
    if art is None:
        not_executed('no sealed forecast', f'{SEALED} is absent')
        return
    rec = _recorded(art)
    before = RR.replay(SEALED, RR.ORIGINAL_REPLAY)
    # A BASELINE THAT DOES NOT PASS IS A FAILURE, NOT A SKIP. The first draft
    # of this file called it not_executed and returned, and a mutation that
    # made the replay top up its source set -- pulling in dk_salaries and
    # hardrock_market_snapshot -- turned this whole function into ZERO CHECKS
    # instead of a named failure. Reading a bail-out as a skip is the exact
    # defect class this repository keeps paying for.
    check('the baseline ORIGINAL_REPLAY passes before anything is injected',
          before.state is State.PASS,
          f'{before.code}: {before.detail}')
    if before.state is not State.PASS:
        return
    base_ids = sorted(before.evidence['partition_ids'])

    # Borrow a real on-disk blob so the intruder is genuinely resolvable.
    donor_src, donor_sha = None, None
    for (s, h), o in ISET.first_observation().items():
        if ISET.blob_for(s, h) is not None:
            donor_src, donor_sha, donor_obs = s, h, o
            break
    check('a real on-disk blob is available to borrow for the injection',
          donor_sha is not None, 'the vintage store is empty, so the '
          'injection below could not be made live')
    if donor_sha is None:
        return
    intruder_id = f'{INTRUDER}@{donor_sha[:16]}'

    real_first, real_blob = ISET.first_observation, ISET.blob_for
    try:
        def seeded_first():
            obs = dict(real_first())
            obs[(INTRUDER, donor_sha)] = dict(donor_obs, source=INTRUDER)
            return obs

        def seeded_blob(source, sha256):
            if source == INTRUDER:
                return real_blob(donor_src, sha256)
            return real_blob(source, sha256)

        ISET.first_observation = seeded_first
        ISET.blob_for = seeded_blob

        # THE PROOF THE INJECTION IS LIVE. Name it, and it resolves.
        widened = RC.build_from_partition_ids(list(rec) + [intruder_id],
                                              art['kickoff_utc'])
        check('the injected source IS resolvable when the seal names it',
              INTRUDER in widened['sources']
              and widened['n_partitions'] == len(rec) + 1,
              f'{widened["n_partitions"]} partition(s) -- if this fails the '
              f'injection did nothing and the check below proves nothing')

        # THE ACTUAL QUESTION. Do not name it, and it cannot get in.
        after = RR.replay(SEALED, RR.ORIGINAL_REPLAY)
    finally:
        ISET.first_observation = real_first
        ISET.blob_for = real_blob

    check('the replay still passes', after.state is State.PASS, after.code)
    if after.state is not State.PASS:
        return
    ids = sorted(after.evidence['partition_ids'])
    check('  the injected source is absent from the replay',
          INTRUDER not in {p.split('@')[0] for p in ids})
    check('  the partition set is byte-identical to the baseline',
          ids == base_ids, f'{len(ids)} vs {len(base_ids)}')
    check('  and the input bundle digest did not move',
          after.evidence['input_bundle_sha256']
          == before.evidence['input_bundle_sha256'])
    check('  the real manifest view is restored',
          ISET.first_observation is real_first
          and ISET.blob_for is real_blob)


def test_c_substitution_is_refused_while_alternatives_are_abundant():
    """Acceptance 4, with the temptation MEASURED rather than asserted.

    `test_replay_contract.py` breaks one recorded id and checks the refusal.
    Its comment says the nearest lawful blob exists. This counts them, so the
    refusal is known to be a refusal-in-the-presence-of-an-alternative and not
    a refusal because there was nothing else to reach for.
    """
    print('\nC. acceptance 4 -- refuses WHILE a substitute sits right there')
    art = _art()
    if art is None:
        not_executed('no sealed forecast', f'{SEALED} is absent')
        return
    rec = _recorded(art)
    obs = ISET.first_observation()

    target = None
    for pid in rec:
        s = pid.split('@')[0]
        alts = [h for (src, h) in obs
                if src == s and h[:16] != pid.split('@')[1]
                and ISET.blob_for(src, h) is not None]
        if alts:
            target, n_alts = pid, len(alts)
            break
    if target is None:
        not_executed('no recorded source has an alternative blob',
                     'there is no substitution to refuse, so nothing to prove')
        return

    src_name = target.split('@')[0]
    print(f'       {src_name}: {n_alts} other resolvable blob(s) on disk')
    check(f'a substitute for {src_name} is genuinely available',
          n_alts > 0)

    broken = [('%s@%s' % (src_name, '0' * 16)) if p == target else p
              for p in rec]
    try:
        got = RC.build_from_partition_ids(broken, art['kickoff_utc'])
        check('the unresolvable partition refuses', False,
              f'it returned {got["n_partitions"]} partition(s) -- it '
              f'substituted one of the {n_alts} available blobs')
    except RC.ReplayRefusal as e:
        check('it REFUSES by name rather than substituting',
              e.code == 'ORIGINAL_PARTITION_UNAVAILABLE', e.code)
        check(f'  with {n_alts} lawful alternative(s) for {src_name} '
              f'sitting on disk, unused', True)
        miss = e.evidence.get('missing') or []
        check('  and names exactly the one partition it could not resolve',
              len(miss) == 1 and miss[0]['partition_id'] == broken[
                  broken.index('%s@%s' % (src_name, '0' * 16))],
              str(miss)[:200])

    # And the whole-source case: drop the source's id entirely. A replay must
    # not quietly return a SMALLER input set either -- a silently narrower
    # bundle is a different forecast just as surely as a substituted one.
    fewer = [p for p in rec if p != target]
    ok = RC.build_from_partition_ids(fewer, art['kickoff_utc'])
    check('dropping a recorded id gives a strictly smaller set, not a refilled '
          'one', ok['n_partitions'] == len(rec) - 1
          and src_name not in ok['sources'],
          f'{ok["n_partitions"]} partition(s), sources {sorted(ok["sources"])}')
    check('  and the runner catches that against the seal\'s own digest',
          IN.bundle_sha256(ok) != art.get('input_bundle_sha256'),
          'a narrower bundle hashed to the sealed digest, which cannot happen')


if __name__ == '__main__':
    test_a_the_pinned_path_cannot_reach_the_selector_at_all()
    test_b_a_source_added_later_cannot_enter_a_replay()
    test_c_substitution_is_refused_while_alternatives_are_abundant()
    print(f'\n{PASSED} passed, {FAILED} failed, '
          f'{len(NOT_EXECUTED)} NOT_EXECUTED')
    for label, why in NOT_EXECUTED:
        print(f'  NOT_EXECUTED: {label} -- {why}')
    sys.exit(1 if FAILED else 0)
