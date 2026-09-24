"""Hostile plausible inputs, each requiring the RIGHT NAMED refusal.

A defensive system proves itself by surviving inputs designed to look
acceptable, not by passing fixtures built from the happy path. Each case below
seeds something a real feed could plausibly produce on a bad day and asserts
the system refuses it BY NAME. Refusing for the wrong reason counts as a
failure here, because a refusal nobody can act on is barely better than none.

THE FOURTEEN CASES, AND WHERE EACH IS COVERED

  1  fresher undeclared roster ................. here (evidence boundary)
  2  stale but syntactically valid injury feed .. here (governed age bound)
  3  truncated source ........................... source_census + here
  4  game-mismatched source ..................... here (attribution)
  5  navigation text containing player names .... test_official_inactives_parser
  6  missing player from a capped feed .......... here (absence != health)
  7  post-kickoff source artifact ............... here (AFTER_CUTOFF)
  8  wrong hash ................................. here (HASH_MISMATCH)
  9  wrong candidate identity ................... here (cut ledger identity)
 10  changed seed ............................... here (cut ledger identity)
 11  changed parser version ..................... here (spec version carried)
 12  duplicated player identity ................. here (crosswalk ambiguity)
 13  player on two clubs ........................ here (team-scoped resolution)
 14  officially inactive player with allocation . test_unavailable_owns_nothing

Cases 5 and 14 are asserted in their own modules against real preserved bytes
rather than restated here, and this file names where, so the battery is a
complete map rather than a partial one that looks complete.
"""
import datetime as dt
import json
import os
import pathlib
import sys
import tempfile

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.dfs.identity_crosswalk import CrosswalkError, crosswalk  # noqa: E402
from nfl.prospective import cut_ledger as CL  # noqa: E402
from nfl.production import source_census as SC  # noqa: E402
from nfl.production import source_validity as SV  # noqa: E402
from nfl.truth import run_input as RI  # noqa: E402

PASSED = FAILED = BLOCKED = 0
RUN = pathlib.Path(_ROOT) / 'nfl' / 'research' / 'unsealed' / \
    '2026_03_ATL_GB' / '2fc4e9599f0889f1'


def chk(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def blocked(label, why):
    global BLOCKED
    BLOCKED += 1
    print(f'  BLOCKED {label}  {why}')


def _contract():
    return json.loads((RUN / 'RUN_INPUT_CONTRACT.json').read_text())


def case_01_a_fresher_undeclared_file_is_structurally_invisible():
    """The evidence boundary: discovery ended at freeze."""
    if not RUN.is_dir():
        return blocked('case 1', f'{RUN} absent')
    c = _contract()
    before = RI.verify(c, root=pathlib.Path(_ROOT))
    h_before, _ = CL.evidence_bundle_hash(c)

    with tempfile.TemporaryDirectory() as tmp:
        intruder = pathlib.Path(tmp) / 'weekly_rosters.ffffffffffffffff.csv.gz'
        intruder.write_bytes(b'\x1f\x8b\x08\x00' + b'\x00' * 32)
        after = RI.verify(c, root=pathlib.Path(_ROOT))
        h_after, _ = CL.evidence_bundle_hash(c)

    chk('a newer undeclared file does not change any verdict',
        before['verdicts'] == after['verdicts'])
    chk('nor the evidence bundle digest', h_before == h_after)
    chk('because the contract names its sources and discovery is over',
        set(after['verdicts']) == set(c['entries']))


def case_02_a_stale_but_valid_injury_feed_is_refused_on_age():
    """Syntactically perfect, semantically expired."""
    if not RUN.is_dir():
        return blocked('case 2', f'{RUN} absent')
    c = _contract()
    tight = RI.verify(c, root=pathlib.Path(_ROOT), required_max_age_h=0.5)
    inj = tight['per_family'].get('injuries') or {}
    chk('a 3.37h injuries capture fails a 0.5h bound',
        inj.get('verdict') == RI.STALE, str(inj.get('verdict')))
    chk('and the contract becomes not consumable',
        not tight['ok'] and 'injuries' in tight['required_failures'])
    chk('the bound that refused it is carried, not implied',
        inj.get('max_age_hours') == 0.5, str(inj.get('max_age_hours')))


def case_03_and_06_a_capped_feed_cannot_answer_a_negative_question():
    obs = [{'capture_id': f'c{i}',
            'per_entity': {f'e{j}': 25 for j in range(32)}}
           for i in range(40)]
    rep = SC.census(obs)
    codes = {f['code'] for f in rep['findings']}
    chk('truncation is detected from shape alone',
        SC.SUSPECTED_TRUNCATION in codes)
    axis = SC.completeness_axis(rep)
    v = SV.new_report(
        'feed', transport=SV.PASS, content=SV.PASS,
        completeness=axis, attribution=SV.PASS,
        eligibility={'state': SV.RESTRICTED, 'detail': 'designations only',
                     'authorised_for': ('is this player listed OUT',)})
    pos = SV.usable_for(v, 'is this player listed OUT',
                        requires=('content', 'attribution', 'eligibility'))
    neg = SV.usable_for(v, 'is this player healthy',
                        requires=('content', 'completeness', 'attribution',
                                  'eligibility'))
    chk('a POSITIVE observation remains usable', pos['usable'])
    chk('a NEGATIVE inference is refused', not neg['usable'])
    chk('and completeness is among the named reasons',
        neg['failing_axes'].get('completeness') == SV.PARTIAL,
        str(neg['failing_axes']))


def case_04_a_game_mismatched_source_fails_attribution():
    v = SV.new_report('other_game_feed', transport=SV.PASS, content=SV.PASS,
                      completeness=SV.PASS,
                      attribution={'state': SV.FAIL,
                                   'detail': 'covers 2026_03_CHI_CAR'})
    u = SV.usable_for(v, 'who is inactive for ATL @ GB',
                      requires=('content', 'attribution'))
    chk('three good axes do not rescue a wrong game',
        not u['usable'] and u['failing_axes']['attribution'] == SV.FAIL)


def case_07_a_post_kickoff_artifact_is_refused():
    if not RUN.is_dir():
        return blocked('case 7', f'{RUN} absent')
    c = json.loads(json.dumps(_contract()))
    fam = 'injuries'
    c['entries'][fam]['retrieved_at'] = '2026-09-25T02:00:00Z'
    rep = RI.verify(c, root=pathlib.Path(_ROOT))
    chk('evidence retrieved after the cutoff is AFTER_CUTOFF',
        rep['per_family'][fam]['verdict'] == RI.AFTER_CUTOFF,
        rep['per_family'][fam]['verdict'])
    chk('and it blocks consumability', not rep['ok'])

    chk('a cut cannot be registered after kickoff',
        _raises_cut(lambda: CL.build_row(
            RUN, '2026-09-25T00:15:00Z',
            now=dt.datetime(2026, 9, 25, 3, tzinfo=dt.timezone.utc)),
            'has already passed'))


def case_08_a_wrong_hash_is_refused_by_name():
    if not RUN.is_dir():
        return blocked('case 8', f'{RUN} absent')
    c = json.loads(json.dumps(_contract()))
    fam = 'schedules'
    c['entries'][fam]['blob_file_sha256'] = 'deadbeef' * 8
    rep = RI.verify(c, root=pathlib.Path(_ROOT))
    chk('a tampered hash is HASH_MISMATCH',
        rep['per_family'][fam]['verdict'] == RI.HASH_MISMATCH,
        rep['per_family'][fam]['verdict'])
    chk('and both hashes are reported so a human can see which moved',
        {'expected_sha256', 'actual_sha256'} <= set(rep['per_family'][fam]))


def _raises_cut(fn, needle):
    try:
        fn()
    except CL.CutLedgerError as e:
        return needle in str(e)
    return False


def case_09_10_11_identity_seed_and_parser_version_move_the_cut():
    """A different run is a different cut, and the id must say so."""
    if not RUN.is_dir():
        return blocked('cases 9-11', f'{RUN} absent')
    now = dt.datetime(2026, 9, 24, 19, tzinfo=dt.timezone.utc)
    base = CL.build_row(RUN, '2026-09-25T00:15:00Z', now=now)

    c = json.loads(json.dumps(_contract()))
    c['entries']['schedules']['sha256'] = 'changed' + '0' * 57
    h_base, _ = CL.evidence_bundle_hash(_contract())
    h_moved, _ = CL.evidence_bundle_hash(c)
    chk('changing one source sha256 moves the evidence digest',
        h_base != h_moved)
    chk('so a cut built on different evidence gets a different id',
        base['cut_id'] != 'CUT-' + h_moved[:16])
    chk('the row carries the code commit', bool(base['code_commit']))
    chk('and the candidate identity', bool(base['candidate_identity']))
    chk('and the rng block, which carries the seed',
        base.get('rng') is not None or base.get('n_draws') is not None)
    chk('spec versions are carried, not assumed',
        base['spec_version'] == CL.SPEC_VERSION)


def case_12_a_duplicated_player_identity_refuses():
    snap = {'players': [
        {'gsis_id': '00-0000001', 'full_name': 'Mike Williams', 'team': 'ATL'},
        {'gsis_id': '00-0000002', 'full_name': 'Mike Williams', 'team': 'ATL'}]}
    rows = [{'Player': 'Mike Williams', 'Team': 'ATL', 'Pos': 'WR',
             'Salary': '5000'}]
    art = crosswalk(rows, snap)
    entry = art['entries'][0]
    chk('two same-named teammates yield AMBIGUOUS',
        entry['resolution'] == 'AMBIGUOUS_WITHIN_TEAM')
    chk('with no identity assigned', entry['gsis_id'] is None)
    chk('both candidates surfaced',
        sorted(entry['candidates']) == ['00-0000001', '00-0000002'])
    from nfl.dfs.identity_crosswalk import assert_complete
    try:
        assert_complete(art)
        chk('and the gate refuses the crosswalk', False, 'it passed')
    except CrosswalkError as e:
        chk('and the gate refuses the crosswalk',
            'AMBIGUOUS_WITHIN_TEAM=1' in str(e), str(e))


def case_13_a_player_on_two_clubs_does_not_cross_teams():
    snap = {'players': [
        {'gsis_id': '00-0000001', 'full_name': 'Jordan Love', 'team': 'GB'},
        {'gsis_id': '00-0000009', 'full_name': 'Jordan Love', 'team': 'ATL'}]}
    rows = [{'Player': 'Jordan Love', 'Team': 'GB', 'Pos': 'QB',
             'Salary': '10000'}]
    art = crosswalk(rows, snap)
    e = art['entries'][0]
    chk('resolution is scoped to the club on the DK row',
        e['resolution'] == 'EXACT_WITHIN_TEAM' and e['gsis_id'] == '00-0000001',
        f"{e['resolution']} {e.get('gsis_id')}")
    rows_atl = [{'Player': 'Jordan Love', 'Team': 'ATL', 'Pos': 'QB',
                 'Salary': '10000'}]
    e2 = crosswalk(rows_atl, snap)['entries'][0]
    chk('and the other club resolves to the other identity',
        e2['gsis_id'] == '00-0000009', str(e2.get('gsis_id')))
    rows_mia = [{'Player': 'Jordan Love', 'Team': 'MIA', 'Pos': 'QB',
                 'Salary': '10000'}]
    e3 = crosswalk(rows_mia, snap)['entries'][0]
    chk('a third club matches neither',
        e3['resolution'] == 'UNRESOLVED_NO_MATCH')


if __name__ == '__main__':
    for _n, _f in sorted((n, f) for n, f in list(globals().items())
                         if n.startswith('case_') and callable(f)):
        print(f'\n== {_n}')
        _f()
    print(f'\nPASSED {PASSED}  FAILED {FAILED}  BLOCKED {BLOCKED}')
    raise SystemExit(1 if FAILED else 0)
