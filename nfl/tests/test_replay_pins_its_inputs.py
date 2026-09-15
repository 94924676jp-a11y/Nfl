"""D23. A written_at cutoff does not pin an input set, and the seal already knows.

THE OBSERVATION

`Q9_SHADOW_DRYRUN_SEAL_LEDGER.jsonl` holds two runs of the same game,
2024_01_ARI_BUF, at the SAME declared consumed clock, written_at
2026-09-12T12:00:00Z, that consumed DIFFERENT inputs:

    sealed 2026-09-12   official_inactives@67511bb2cfc1e9f3
    replay 2026-09-15   official_inactives@fefbd73647bb1e1d

and likewise for depth_charts, espn_injuries_json, official_injury_report and
schedules.

THE DIAGNOSIS, AND THE SELECTOR IS NOT AT FAULT

`inputs.bundle` selects the latest capture with `retrieved_at <= written_at`,
which is correct and is what makes `retrieved_at <= written_at` hold by
construction. Both blobs satisfy it:

    67511bb2cfc1e9f3   retrieved 2026-09-11T00:44:00Z   <= the clock
    fefbd73647bb1e1d   retrieved 2026-09-12T11:34:53Z   <= the clock

The second is genuinely later and genuinely lawful. It simply DID NOT EXIST in
this branch's manifest when the seal was written: measured, it appears 0 times
in the manifest at 382556b, 0 times at the common ancestor 1034e272, and 3 times
on main. Reconciling with main added it, dated in the past relative to the clock.

So the failure is not the selector, not the clock, and not the merge. It is that

    A `written_at` CUTOFF DOES NOT PIN AN INPUT SET WHEN THE MANIFEST IS
    APPEND-ONLY AND CAN GAIN ROWS DATED BEFORE THAT CUTOFF.

A clock bounds selection. It does not determine it, because what is selectable
is a property of the manifest's CONTENT, and the content grows.

WHY THIS MATTERS MORE THAN ONE DRY RUN. Every chronological comparison in this
project re-runs a historical window. If each re-run silently re-selects its
inputs as the corpus grows, then two arms compared on "the same" 2024 game may
not have seen the same 2024 game, and no before-and-after is reproducible. That
is the whole evidentiary basis of V2.

THE FIX IS ALREADY IN THE ARTIFACT. Every seal records
`consumed_partition_ids`. A REPLAY must reproduce from those recorded ids; only
a NEW FORECAST re-runs selection. Re-running selection and calling the result a
replay produces a different forecast wearing the same clock -- exactly what the
fingerprint discipline exists to prevent.

SECTION C FAILS ON PURPOSE. It is the defect: no replay path takes recorded
partition ids as its input. Do not delete it and do not weaken it to green.

Run standalone:  python3.12 nfl/tests/test_replay_pins_its_inputs.py
"""
import json
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

PASSED = FAILED = 0
NOT_EXECUTED = []
ROOT = pathlib.Path(__file__).resolve().parents[2]
LEDGER = (ROOT / 'nfl' / 'prospective' / 'q9shadow'
          / 'Q9_SHADOW_DRYRUN_SEAL_LEDGER.jsonl')
MANIFEST = ROOT / 'nfl' / 'vintage_manifest.jsonl'
GAME = '2024_01_ARI_BUF'


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


def _rows():
    out = []
    if not LEDGER.exists():
        return out
    for line in LEDGER.read_text().splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _by_clock(game):
    """Ledger rows for one game, grouped by declared written_at."""
    groups = {}
    for r in _rows():
        if r.get('game_id') != game:
            continue
        groups.setdefault(r.get('written_at'), []).append(r)
    return groups


# --------------------------------------------------------------------------
def test_a_the_same_clock_produced_two_different_input_sets():
    """THE EVIDENCE."""
    print('\nA. one game, one declared clock, two input sets')
    groups = _by_clock(GAME)
    if not groups:
        not_executed(f'no ledger rows for {GAME}',
                     'the dry-run ledger is absent or carries another game')
        return
    for clock, rows in sorted(groups.items()):
        sets = {tuple(sorted(r.get('consumed_partition_ids') or []))
                for r in rows}
        print(f'       written_at={clock}: {len(rows)} row(s), '
              f'{len(sets)} distinct input set(s)')
        if len(sets) > 1:
            a, b = sorted(sets)[:2]
            diff = sorted(set(a) ^ set(b))
            check(f'  {clock} produced MORE THAN ONE input set',
                  True)
            print(f'       differing partitions ({len(diff)}):')
            for d in diff[:12]:
                print(f'         {d}')
            return
    check('at least one clock shows two different input sets', False,
          'if this passes the drift is gone and D23 needs re-measuring, '
          'not deleting')


def test_b_every_selected_partition_was_lawful_so_the_selector_is_not_at_fault():
    """The selector did its job. The clock is what fails to pin."""
    print('\nB. every pick obeyed the clock -- the selector is correct')
    groups = _by_clock(GAME)
    if not groups:
        not_executed('no ledger rows', 'nothing to check')
        return
    addr_time = {}
    for line in MANIFEST.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        v = r.get('value') or {}
        blob = v.get('blob')
        if not blob:
            continue
        ra = ((v.get('provenance') or {}).get('retrieved_at')
              or v.get('retrieved_at'))
        sha = v.get('sha256') or ''
        if ra and sha:
            addr_time.setdefault(sha[:16], ra)

    late = []
    checked = 0
    for clock, rows in groups.items():
        if not clock:
            continue
        cut = str(clock).replace('Z', '')
        for r in rows:
            for pid in (r.get('consumed_partition_ids') or []):
                addr = pid.split('@')[-1]
                ra = addr_time.get(addr)
                if ra is None:
                    continue
                checked += 1
                if str(ra)[:19] > cut[:19]:
                    late.append((pid, ra, clock))
    check(f'all {checked} resolvable picks were retrieved at or before their '
          f'declared clock', not late, str(late[:3]))
    check('  so the drift is NOT a clock violation', not late)


def test_c_BUG_no_replay_path_reproduces_from_the_recorded_partitions():
    """FAILS ON PURPOSE. The seal records the answer and nothing consumes it."""
    print('\nC. BUG -- the recorded partition ids are written, never read back')
    rows = [r for r in _rows() if r.get('consumed_partition_ids')]
    check('the seals DO record which partitions were consumed',
          bool(rows), f'{len(rows)} row(s) carry consumed_partition_ids')

    # THE STRUCTURAL CHECK, NOT A TEXT SEARCH.
    #
    # My first cut of this section grepped for the field name and called any
    # line containing an `=` a "consumer". It matched
    # `identity={}, consumed_partition_ids=tuple(` -- a CONSTRUCTOR argument --
    # and reported the defect repaired. That is the same textual-heuristic
    # failure this file is about, committed inside the test for it. The actual
    # use in dryrun.py reads the field out of an artifact only to build a Seal
    # for the re-seal REFUSAL test; it never reaches selection.
    #
    # So ask the question structurally: does the function that builds an input
    # set accept recorded partition ids at all? If its signature cannot take
    # them, no caller can pin a rebuild, whatever the text says.
    import inspect
    from nfl.prospective.q9shadow import inputs as INP
    sig = inspect.signature(INP.bundle)
    params = list(sig.parameters)
    print(f'       inputs.bundle{sig}')
    pinning = [q for q in params
               if 'partition' in q.lower() or 'pin' in q.lower()
               or 'consumed' in q.lower()]
    check('inputs.bundle can be given the partitions to reproduce',
          bool(pinning),
          f'REPLAY_RE_SELECTS: its parameters are {params}. None of them '
          f'accepts a recorded input set, so every call re-runs selection '
          f'against whatever the manifest holds TODAY. A clock BOUNDS '
          f'selection; only the recorded partitions DETERMINE it. The seal '
          f'stores the answer and nothing can consume it. See D23.')


if __name__ == '__main__':
    test_a_the_same_clock_produced_two_different_input_sets()
    test_b_every_selected_partition_was_lawful_so_the_selector_is_not_at_fault()
    test_c_BUG_no_replay_path_reproduces_from_the_recorded_partitions()
    print(f'\n{PASSED} passed, {FAILED} failed, {len(NOT_EXECUTED)} NOT_EXECUTED')
    for label, why in NOT_EXECUTED:
        print(f'  NOT_EXECUTED: {label} -- {why}')
    sys.exit(1 if FAILED else 0)
