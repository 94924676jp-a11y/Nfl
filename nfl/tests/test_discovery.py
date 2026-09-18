"""CONTINUOUS_DISCOVERY: the inspection is executable, and it refuses to score.

WHY A TOOL AND NOT A CHECKLIST, TESTED

`INFORMATION_GAP_REGISTRY.json` records "MEASURED: both 404 for 2026 as of
2026-09-08" for the participation sources. The sibling `injuries` source began
publishing 2026-09-07 and this repository holds nine content-addressed vintages
of it -- and nothing said so, because the registry has no freshness field and
nothing re-read it. A hand-run checklist would have missed it again; the
`newly_publishing` detector is the check that did not.

THE TWO THINGS THIS FILE REALLY GUARDS

**That the detectors fire.** A discovery pass that returns an empty list
because its detectors are broken is worse than no discovery pass, and it looks
identical from the outside. Each detector below is driven against a synthetic
input that must trigger it, and against one that must not.

**That nothing is scored.** The directive ranks by downstream impact x
uncertainty x measurability x expected value of information. None of the four
is measurable from this repository, so the tool emits evidence and the ranking
lives in WORK_QUEUE.md in words. A number would be a silent constant.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, 'nfl', 'tools'))

import discovery as D                                             # noqa: E402

PASSED = FAILED = 0
ART = pathlib.Path(_ROOT) / 'nfl' / 'DISCOVERY.json'


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


# =========================================================== the detectors

def test_newly_publishing_needs_both_halves():
    """Recently started AND previously recorded absent. Either alone is noise."""
    both = {'injuries': {'days_since_first_success': 5.0,
                         'first_success_utc': '2026-09-07T00:00:00+00:00',
                         'n_distinct_blobs': 9,
                         'absent_codes_recorded': {'SOURCE_NOT_YET_PUBLISHED': 40}}}
    check('a source that started recently AND was recorded absent fires',
          len(D.newly_publishing(both)) == 1, str(D.newly_publishing(both)))
    new_only = {'x': {'days_since_first_success': 1.0,
                      'first_success_utc': 'z', 'n_distinct_blobs': 1,
                      'absent_codes_recorded': {}}}
    check('a merely new source does NOT fire -- that is just a new source',
          D.newly_publishing(new_only) == [], str(D.newly_publishing(new_only)))
    old_absent = {'y': {'days_since_first_success': 400.0,
                        'first_success_utc': 'z', 'n_distinct_blobs': 3,
                        'absent_codes_recorded': {'404': 2}}}
    check('a long-publishing source that was once absent does NOT fire -- '
          'that is history', D.newly_publishing(old_absent) == [],
          str(D.newly_publishing(old_absent)))


def test_the_real_tree_detects_the_injuries_source():
    """The finding this tool was written for, against the real manifest."""
    caps = D.captures()
    check('the capture scan returns per-source records',
          isinstance(caps, dict) and 'injuries' in caps,
          str(sorted(caps)[:6]) if isinstance(caps, dict) else str(caps))
    if not isinstance(caps, dict) or 'injuries' not in caps:
        return
    inj = caps['injuries']
    check('injuries has succeeded', inj['first_success_utc'] is not None,
          str(inj['first_success_utc']))
    check('it carries more than one content-addressed vintage, so a '
          'point-in-time read is possible', inj['n_distinct_blobs'] >= 2,
          str(inj['n_distinct_blobs']))
    check('and the repository still records it as having been absent',
          bool(inj['absent_codes_recorded']),
          str(inj['absent_codes_recorded']))
    fired = [n['source'] for n in D.newly_publishing(caps)]
    check('so the detector fires on it', 'injuries' in fired, str(fired))


def test_a_gap_claim_past_its_horizon_is_surfaced():
    gs = D.gaps()
    check('the gap registry parses', len(gs) >= 5, str(len(gs)))
    dated = [g for g in gs if g['newest_date_in_claim']]
    check('at least one gap carries a date in its claim', dated, str(len(dated)))
    check('a claim age is computed for every dated gap',
          all(g['claim_age_days'] is not None for g in dated))
    check('the horizon is declared, not hidden in a comparison',
          isinstance(D.GAP_RECHECK_DAYS, int) and D.GAP_RECHECK_DAYS > 0,
          str(D.GAP_RECHECK_DAYS))
    stale = [g['id'] for g in gs if g['stale_beyond_recheck_horizon']]
    check('the participation gap is among the stale ones',
          'GAP-2026-PARTICIPATION' in stale, str(stale))
    check('a gap carrying no date at all is flagged as such rather than '
          'treated as fresh',
          all(isinstance(g['has_no_date_at_all'], bool) for g in gs))


def test_a_critical_falsified_assumption_without_a_successor_is_surfaced():
    a = D.assumptions()
    if not check('the registry loaded', a.get('state') != 'NOT_MEASURED',
                 str(a.get('why'))):
        return
    rows = {r['id']: r for r in a['assumptions']}
    check('A1 is falsified and critical',
          rows['A1_APPEARANCE_CERTAINTY']['status'] == 'FALSIFIED'
          and rows['A1_APPEARANCE_CERTAINTY']['criticality'] == 'CRITICAL',
          str(rows['A1_APPEARANCE_CERTAINTY']['status']))
    check('A2 is falsified and HAS a successor spec',
          rows['A2_PROPORTIONAL_REDISTRIBUTION']['has_successor_spec'] is True)
    # THE RULE, NOT THE STATE. A first version asserted that A1 IS surfaced.
    # Writing A1_SUCCESSOR_SPEC.md made the detector correctly fall silent and
    # the test correctly fail -- but it had encoded a moment rather than a
    # behaviour, so it would have failed again the next time the repository
    # improved. What is pinned now is that `has_successor_spec` tracks the
    # filesystem and that the detector fires exactly when it is false.
    spec_dir = pathlib.Path(_ROOT) / 'nfl' / 'research' / 'assumptions'
    on_disk = {f.name for f in spec_dir.glob('*')}
    for r in a['assumptions']:
        stem = r['id'].split('_')[0]
        expect = any(n.startswith(stem) and 'SUCCESSOR' in n.upper()
                     for n in on_disk)
        check(f'{r["id"]}: has_successor_spec tracks the filesystem',
              r['has_successor_spec'] == expect,
              f'{r["has_successor_spec"]} against {expect}')
    live = [c['subject'] for c in D.candidates(
        {'newly_publishing': [], 'gaps': [], 'assumptions': a,
         'technical_debt': []})
        if c['trigger'] == 'CRITICAL_ASSUMPTION_FALSIFIED_WITHOUT_SUCCESSOR']
    should = [r['id'] for r in a['assumptions']
              if r['status'] == 'FALSIFIED' and r['criticality'] == 'CRITICAL'
              and not r['has_successor_spec']]
    check('the detector fires on exactly the assumptions that qualify',
          sorted(live) == sorted(should), f'{sorted(live)} vs {sorted(should)}')
    synth = {'assumptions': [{'id': 'AX', 'status': 'FALSIFIED',
                              'criticality': 'CRITICAL', 'test': 't',
                              'has_evidence': True, 'downstream': ['a'],
                              'has_successor_spec': False, 'untested': False}]}
    fired = [c['subject'] for c in D.candidates(
        {'newly_publishing': [], 'gaps': [], 'assumptions': synth,
         'technical_debt': []})]
    check('and it FIRES on a synthetic falsified CRITICAL with no successor',
          'AX' in fired, str(fired))


def test_the_untested_critical_detector_fires_only_when_it_should():
    """It does NOT fire on the real tree today, and that is the correct state.

    A first version of this test asserted A4 was untested. It is not: A4 names
    `game_offense_coupling.run`. The two assumptions with `NOT_YET_WRITTEN`
    tests are A3 and A5, and both are MATERIAL rather than CRITICAL, so the
    detector is right to stay silent. The test was wrong and the tool was not.

    So the real check is a pair: silent on the tree as it stands, and firing on
    a synthetic CRITICAL row whose test is unwritten. A detector only ever
    observed silent is indistinguishable from a broken one.
    """
    a = D.assumptions()
    if a.get('state') == 'NOT_MEASURED':
        check('the registry loaded', False, str(a.get('why')))
        return
    rows = {r['id']: r for r in a['assumptions']}
    check('A4 is CRITICAL and its test IS written',
          rows['A4_STATIC_TEAM_VOLUME_SUFFICIENCY']['untested'] is False
          and rows['A4_STATIC_TEAM_VOLUME_SUFFICIENCY']['criticality']
          == 'CRITICAL', str(rows['A4_STATIC_TEAM_VOLUME_SUFFICIENCY']['test']))
    check('the assumptions with unwritten tests are A3 and A5',
          sorted(r['id'] for r in a['assumptions'] if r['untested'])
          == ['A3_ROLE_CONTINUITY_ACROSS_REGIME_CHANGE',
              'A5_TD_CONVERSION_PORTABILITY'],
          str([r['id'] for r in a['assumptions'] if r['untested']]))
    check('and both are MATERIAL, not CRITICAL',
          all(r['criticality'] == 'MATERIAL'
              for r in a['assumptions'] if r['untested']))
    live = {c['trigger'] for c in D.candidates(
        {'newly_publishing': [], 'gaps': [], 'assumptions': a,
         'technical_debt': []})}
    check('so the untested-critical detector is correctly SILENT today',
          'CRITICAL_ASSUMPTION_UNTESTED' not in live, str(live))
    synth = {'assumptions': [{'id': 'AX', 'status': 'DECLARED',
                              'criticality': 'CRITICAL',
                              'test': 'NOT_YET_WRITTEN', 'has_evidence': False,
                              'downstream': ['a', 'b'],
                              'has_successor_spec': True, 'untested': True}]}
    cands = D.candidates({'newly_publishing': [], 'gaps': [],
                          'assumptions': synth, 'technical_debt': []})
    kinds = {c['trigger'] for c in cands}
    check('but it FIRES on a synthetic CRITICAL assumption with no test',
          'CRITICAL_ASSUMPTION_UNTESTED' in kinds, str(kinds))
    untested = [c for c in cands
                if c['trigger'] == 'CRITICAL_ASSUMPTION_UNTESTED']
    check('and it says measurability is UNESTABLISHED rather than high',
          all('unestablished' in c['measurability_evidence'].lower()
              for c in untested), str([c['measurability_evidence']
                                       for c in untested]))


def test_an_empty_signal_set_produces_no_candidates():
    """"Nothing found" must be reachable, or the tool always finds something."""
    empty = D.candidates({'newly_publishing': [], 'gaps': [],
                          'assumptions': {'assumptions': []},
                          'technical_debt': []})
    check('no signals means no candidates', empty == [], str(empty))


# =========================================================== the refusals

def test_the_tool_does_not_score_anything():
    d = json.loads(ART.read_text()) if ART.exists() else D.build()
    check('every candidate declines to rank itself',
          all('NOT SCORED HERE' in c['ranking'] for c in d['candidates']),
          str([c['ranking'] for c in d['candidates']][:2]))
    check('and points at the file that does rank',
          all('WORK_QUEUE' in c['ranking'] for c in d['candidates']))
    check('the reason is stated in the artifact, not only in the module',
          'silent constant' in d['ranking_rule'], d['ranking_rule'][:80])
    check('an empty result is declared a valid answer',
          'monitoring' in d['empty_is_a_result'], d['empty_is_a_result'][:80])
    for c in d['candidates']:
        check(f'{c["subject"]}: carries impact and measurability EVIDENCE, '
              f'not scores',
              isinstance(c['impact_evidence'], str)
              and isinstance(c['measurability_evidence'], str))
        break


def test_the_prospective_count_does_not_pretend_to_be_graded_units():
    p = D.prospective()
    check('the prospective section counts blocks and games',
          'n_graded_blocks' in p and 'captured_game_outcomes' in p, str(p))
    check('and says plainly that these are not graded units against the floor',
          'not the same thing' in p['note'], p['note'][:90])
    check('the 300-unit floor is named so the distance is visible',
          '300' in p['note'])


def test_the_artifact_is_current_with_the_queue_it_feeds():
    check('DISCOVERY.json exists', ART.exists(), str(ART))
    if not ART.exists():
        return
    d = json.loads(ART.read_text())
    live = D.build()
    check('it names its generator', d['generated_by'] == D.GENERATOR)
    check('the detected candidate subjects match a live run',
          sorted(c['subject'] for c in d['candidates'])
          == sorted(c['subject'] for c in live['candidates']),
          'regenerate: python3.12 nfl/tools/discovery.py --write')
    q = (pathlib.Path(_ROOT) / 'nfl' / 'WORK_QUEUE.md').read_text()
    check('every detected candidate subject is either queued or already '
          'named in the queue',
          all(c['subject'] in q or c['trigger'] in q
              for c in live['candidates']),
          str([c['subject'] for c in live['candidates']
               if c['subject'] not in q and c['trigger'] not in q]))


def test_the_queue_ranks_in_words_and_names_all_four_factors():
    q = (pathlib.Path(_ROOT) / 'nfl' / 'WORK_QUEUE.md').read_text()
    for f in ('impact', 'uncertainty', 'measurability', 'EVI'):
        check(f'the queue states {f} for its ranked items', f in q)
    check('and it says an empty candidate list is a result',
          'empty candidate list is a result' in q.lower()
          or 'An empty candidate list is a result' in q)
    check('and records why A3 stepped back rather than leaving it unexplained',
          'A3 stepping back' in q or 'not reordered for novelty' in q)
