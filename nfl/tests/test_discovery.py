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

import datetime as dt
import json
import os
import re
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


def _reg(gaps):
    """A synthetic gap registry on disk, so the rule is tested, not the day."""
    fd, name = tempfile.mkstemp(suffix='.json')
    os.close(fd)
    pathlib.Path(name).write_text(json.dumps({'gaps': gaps}))
    return name


def _ago(days):
    return (dt.datetime.now(dt.timezone.utc)
            - dt.timedelta(days=days)).isoformat()


def test_the_horizon_clock_runs_on_the_evidence_not_on_the_reading():
    """The defect DISC-3 exists to stop.

    "MEASURED: both 404 for 2026 as of 2026-09-08" survived snap_counts
    publishing on 2026-09-10. Re-reading that sentence a hundred times would
    not have found it, so a recheck that reads an unchanged file must not
    reset the clock. `last_rechecked_utc` says somebody looked;
    `evidence_as_of_utc` says how new what they saw was, and the horizon is
    measured against the second.
    """
    name = _reg([
        {'id': 'LOOKED-TODAY-AT-OLD-EVIDENCE', 'action': 'HOLD',
         'last_rechecked_utc': _ago(0), 'evidence_as_of_utc': _ago(30),
         'recheck_horizon_days': 7, 'recheck_executable_here': True},
        {'id': 'LOOKED-LONG-AGO-AT-FRESH-EVIDENCE', 'action': 'HOLD',
         'last_rechecked_utc': _ago(60), 'evidence_as_of_utc': _ago(1),
         'recheck_horizon_days': 7, 'recheck_executable_here': True},
    ])
    try:
        g = {x['id']: x for x in D.gaps(name)}
        check('a gap read today whose EVIDENCE is 30 days old is past its '
              '7-day horizon',
              g['LOOKED-TODAY-AT-OLD-EVIDENCE']['recheck_state']
              == 'PAST_HORIZON',
              g['LOOKED-TODAY-AT-OLD-EVIDENCE']['recheck_state'])
        check('and a gap nobody has read for 60 days whose EVIDENCE is one '
              'day old is CURRENT',
              g['LOOKED-LONG-AGO-AT-FRESH-EVIDENCE']['recheck_state']
              == 'CURRENT',
              g['LOOKED-LONG-AGO-AT-FRESH-EVIDENCE']['recheck_state'])
        check('the age reported is the evidence age, not the reading age',
              g['LOOKED-TODAY-AT-OLD-EVIDENCE']['claim_age_days'] > 29)
    finally:
        os.unlink(name)


def test_a_recheck_that_cannot_be_run_here_is_assigned_not_merely_stale():
    """Blocked for both of us, or assigned to one of us. They are not the same.

    An assigned recheck past its horizon is still past its horizon -- it does
    not get to be quiet because somebody else owes it -- but it must say who
    owes it, so it is never left standing as a fact.
    """
    name = _reg([
        {'id': 'MINE', 'action': 'HOLD', 'evidence_as_of_utc': _ago(30),
         'recheck_horizon_days': 7, 'recheck_executable_here': True},
        {'id': 'THEIRS', 'action': 'BLOCKED', 'evidence_as_of_utc': _ago(30),
         'recheck_horizon_days': 7, 'recheck_executable_here': False,
         'recheck_assignment': 'OUT-999'},
    ])
    try:
        g = {x['id']: x for x in D.gaps(name)}
        check('a recheck this executor can run is PAST_HORIZON',
              g['MINE']['recheck_state'] == 'PAST_HORIZON',
              g['MINE']['recheck_state'])
        check('one it cannot is ASSIGNED_PAST_HORIZON',
              g['THEIRS']['recheck_state'] == 'ASSIGNED_PAST_HORIZON',
              g['THEIRS']['recheck_state'])
        check('and it carries the assignment rather than a bare status',
              g['THEIRS']['recheck_assignment'] == 'OUT-999')
        cands = D.candidates({'newly_publishing': [], 'gaps': list(g.values()),
                              'assumptions': {}, 'technical_debt': []})
        trig = {c['subject']: c['trigger'] for c in cands}
        check('both are surfaced as candidates -- assigned is not silent',
              set(trig) == {'MINE', 'THEIRS'}, str(trig))
        check('and the assigned one is surfaced under its own trigger',
              trig['THEIRS'] == 'GAP_RECHECK_ASSIGNED_AND_PAST_HORIZON',
              trig['THEIRS'])
    finally:
        os.unlink(name)


def test_an_undated_gap_cannot_hide_inside_any_horizon():
    """A claim with no date never ages, so no horizon can ever reach it."""
    name = _reg([{'id': 'UNDATED', 'action': 'HOLD',
                  'evidence_status': 'it is known to be so'}])
    try:
        g = D.gaps(name)[0]
        check('an undated gap is flagged', g['has_no_date_at_all'] is True)
        check('and its state is UNDATED, not CURRENT',
              g['recheck_state'] == 'UNDATED', g['recheck_state'])
        cands = D.candidates({'newly_publishing': [], 'gaps': [g],
                              'assumptions': {}, 'technical_debt': []})
        check('and it is surfaced under its own trigger',
              [c['trigger'] for c in cands] == ['GAP_CLAIM_CARRIES_NO_DATE'],
              str([c['trigger'] for c in cands]))
    finally:
        os.unlink(name)


def test_a_declared_horizon_overrides_the_default():
    """Horizons are per gap because the facts move at different speeds.

    Two days for a weekly-published file; ninety for an unrun experiment that
    does not age at all. A single constant would either spam the short ones or
    sleep through them.
    """
    name = _reg([
        {'id': 'FAST', 'action': 'HOLD', 'evidence_as_of_utc': _ago(3),
         'recheck_horizon_days': 2, 'recheck_executable_here': True},
        {'id': 'SLOW', 'action': 'HOLD', 'evidence_as_of_utc': _ago(3),
         'recheck_horizon_days': 90, 'recheck_executable_here': True},
        {'id': 'UNDECLARED', 'action': 'HOLD', 'evidence_as_of_utc': _ago(3),
         'recheck_executable_here': True},
    ])
    try:
        g = {x['id']: x for x in D.gaps(name)}
        check('a 2-day horizon catches 3-day-old evidence',
              g['FAST']['recheck_state'] == 'PAST_HORIZON')
        check('a 90-day horizon does not', g['SLOW']['recheck_state']
              == 'CURRENT')
        check('an undeclared horizon falls back to the declared default and '
              'says so', g['UNDECLARED']['recheck_horizon_days']
              == D.GAP_RECHECK_DAYS
              and g['UNDECLARED']['recheck_horizon_basis'] == 'default')
        check('the default is declared, not hidden in a comparison',
              isinstance(D.GAP_RECHECK_DAYS, int) and D.GAP_RECHECK_DAYS > 0,
              str(D.GAP_RECHECK_DAYS))
    finally:
        os.unlink(name)


def test_the_real_registry_carries_freshness_on_every_gap():
    """DISC-3's acceptance criteria, against the registry that ships."""
    gs = D.gaps()
    check('the gap registry parses', len(gs) >= 5, str(len(gs)))
    undated = [g['id'] for g in gs if g['has_no_date_at_all']]
    check('no gap ships undated', not undated, str(undated))
    proxy = [g['id'] for g in gs if g['age_basis'] != 'evidence_as_of_utc']
    check('every gap dates its EVIDENCE explicitly rather than leaving the '
          'tool to scrape a date out of prose', not proxy, str(proxy))
    nohz = [g['id'] for g in gs
            if g['recheck_horizon_basis'] != 'declared']
    check('every gap declares its own horizon', not nohz, str(nohz))
    nolook = [g['id'] for g in gs if not g['last_rechecked_utc']]
    check('every gap records when it was last rechecked', not nolook,
          str(nolook))
    reg = json.loads((pathlib.Path(_ROOT) / 'nfl'
                      / 'INFORMATION_GAP_REGISTRY.json').read_text())
    for g in reg['gaps']:
        check(f'{g["id"]} says why its horizon is what it is',
              bool((g.get('recheck_horizon_basis') or '').strip()))
        check(f'{g["id"]} names what was read to recheck it',
              bool((g.get('recheck_method') or '').strip()))


def test_an_unrunnable_recheck_names_an_outbox_entry_that_exists():
    """Never blocked on something outside this repository without asking.

    The project rule is that a recheck needing bytes this executor cannot
    fetch is ASSIGNED with an outbox entry. An assignment naming an entry
    nobody wrote is worse than no assignment, because it reads as discharged.
    """
    reg = json.loads((pathlib.Path(_ROOT) / 'nfl'
                      / 'INFORMATION_GAP_REGISTRY.json').read_text())
    outbox = (pathlib.Path(_ROOT) / 'docs' / 'AGENT_OUTBOX.md').read_text()
    external = [g for g in reg['gaps']
                if g.get('recheck_executable_here') is False]
    check('some gaps are honestly marked not-executable here', external,
          'if none, either the flag is unused or the claim is too good')
    for g in external:
        a = g.get('recheck_assignment') or ''
        check(f'{g["id"]} names an assignment', bool(a.strip()))
        ids = re.findall(r'OUT-\d+', a)
        check(f'{g["id"]} names at least one OUT- identifier', bool(ids), a)
        for i in ids:
            check(f'{g["id"]} assignment {i} exists in the outbox',
                  i in outbox, i)


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
