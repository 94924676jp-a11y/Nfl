"""P7: SYSTEM_STATE.json is generated, and CURRENT_STATE.md is derived from it.

THE DEFECT

`CURRENT_STATE.md` was hand-written on 2026-09-07. Read on 2026-09-18 it still
said "1,230 assertions across 19 suites, 0 failing"; the suite was 1,944
functions and 10,335 checks with 61 failing. It said "No predictive model",
gave the branch as `main @ a559da2`, and counted down to a kickoff eight days
past. Every one of those numbers existed elsewhere in the repository and had
been retyped. Prose does not move when the repository does.

Two independently maintained statements of one truth is the defect. One
generated from the other is the repair, and the tests below are what make the
repair hold: a stale generated file FAILS rather than describing a tree that
no longer exists.

WHAT IS DELIBERATELY NOT ASSERTED HERE

That any particular number is correct. A test that pinned "modules == 179"
would be a third hand-maintained copy of the same truth and would go stale the
same way. What is asserted is that the file matches a live regeneration, that
measurements and declarations are kept apart, and that an unmeasurable claim
carries a stated reason it cannot be measured.
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

import system_state as SS                                         # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def _live():
    return SS.build()


# ================================================= the generated artifacts

def test_system_state_exists_and_names_its_generator():
    p = pathlib.Path(_ROOT) / 'SYSTEM_STATE.json'
    check('SYSTEM_STATE.json exists', p.exists(), str(p))
    if not p.exists():
        return
    d = json.loads(p.read_text())
    check('it names the generator', d.get('generated_by') == SS.GENERATOR,
          str(d.get('generated_by')))
    check('it carries a spec version',
          d.get('spec_version') == SS.SPEC_VERSION, str(d.get('spec_version')))
    check('it separates measured from declared',
          'measured' in d and 'declared' in d, str(sorted(d)))
    check('and it states the rule for reading the two apart',
          'Do not quote one as the other' in (d.get('reading_rule') or ''),
          (d.get('reading_rule') or '')[:80])


def test_the_committed_state_is_not_stale():
    """The whole point. A stale generated file fails rather than misleads."""
    p = pathlib.Path(_ROOT) / 'SYSTEM_STATE.json'
    if not p.exists():
        check('SYSTEM_STATE.json exists', False, str(p))
        return
    on_disk = json.loads(p.read_text())['measured']
    live = _live()['measured']
    hint = 'regenerate: python3.12 nfl/tools/system_state.py --write'
    # NOT AN EQUALITY, AND THE REASON IS STRUCTURAL: a file cannot record the
    # hash of the commit that contains it. Asserting `recorded == HEAD` would
    # fail on every commit the instant it was made, and a test that is red by
    # construction gets disabled. What IS asserted is that the recorded HEAD
    # is an ancestor of the current one -- so a state file generated on
    # another branch, or from a future the tree has not reached, still fails.
    # Everything else below is a measurement that only an EDIT changes, and
    # those are asserted exactly.
    import subprocess
    rec = on_disk['git']['head']
    anc = subprocess.run(
        ['git', 'merge-base', '--is-ancestor', rec, 'HEAD'],
        cwd=_ROOT, capture_output=True).returncode == 0
    check('the recorded HEAD is this branch\'s HEAD or an ancestor of it',
          rec == live['git']['head'] or anc,
          f'{rec[:8]} is not reachable from {live["git"]["head"][:8]}; {hint}')
    check('the code inventory matches a live count',
          on_disk['code']['TOTAL'] == live['code']['TOTAL'],
          f'{on_disk["code"]["TOTAL"]} vs {live["code"]["TOTAL"]}; {hint}')
    check('the assumption statuses match the registry now',
          on_disk['assumptions'].get('by_status')
          == live['assumptions'].get('by_status'), hint)
    check('the DAG audit state matches a live audit',
          on_disk['dependency_dag'].get('audit_code')
          == live['dependency_dag'].get('audit_code'), hint)
    check('the capture manifest row count matches',
          on_disk['capture'].get('manifest_rows')
          == live['capture'].get('manifest_rows'), hint)
    check('the work queue statuses match WORK_QUEUE.md now',
          [i['status'] for i in on_disk['work_queue']['items']]
          == [i['status'] for i in live['work_queue']['items']], hint)


def test_current_state_is_rendered_from_system_state():
    md = pathlib.Path(_ROOT) / 'CURRENT_STATE.md'
    check('CURRENT_STATE.md exists', md.exists(), str(md))
    if not md.exists():
        return
    txt = md.read_text()
    check('it says it is generated and must not be hand-edited',
          'Do not hand-edit' in txt and SS.GENERATOR in txt)
    check('it is byte-identical to a render of the committed state',
          txt == SS.render(json.loads(
              (pathlib.Path(_ROOT) / 'SYSTEM_STATE.json').read_text())),
          'regenerate: python3.12 nfl/tools/system_state.py --write')


def test_no_number_in_the_rendered_file_is_typed_by_a_person():
    """The renderer may format; it may not author a figure.

    Checked structurally: every number the file states about the system comes
    from a `measured` value, so changing the repository changes the file. The
    screen below is weak -- it looks for the measured totals appearing in the
    text -- and it is weak on purpose, because the strong version would be a
    second copy of the numbers.
    """
    md = (pathlib.Path(_ROOT) / 'CURRENT_STATE.md').read_text()
    live = _live()['measured']
    check('the live module count appears in the rendered file',
          str(live['code']['TOTAL']['modules']) in md,
          str(live['code']['TOTAL']['modules']))
    check('the live manifest row count appears',
          str(live['capture']['manifest_rows']) in md)
    check('the live HEAD appears', live['git']['head_short'] in md)
    if live['suite'].get('totals'):
        check('the live suite check count appears',
              str(live['suite']['totals']['checks']) in md)


# ==================================================== the declared section

def test_a_declaration_without_its_required_fields_is_refused():
    d = tempfile.mkdtemp(prefix='decl_')
    p = pathlib.Path(d) / 'STATE_DECLARATIONS.md'
    p.write_text('## ID: X\n- **claim**: something is true\n'
                 '- **declared_by**: me\n- **declared_at**: today\n'
                 '- **status**: STANDING\n')
    items = SS.read_declarations(p)
    check('the declaration parses', len(items) == 1, str(items))
    try:
        SS.validate_declarations(items)
        check('a declaration with no stated reason is refused', False,
              'no raise')
    except SS.DeclarationError as exc:
        check('a declaration missing why_not_measurable is refused',
              'DECLARATION_INCOMPLETE' in str(exc)
              and 'why_not_measurable' in str(exc), str(exc)[:160])


def test_every_real_declaration_is_complete():
    items = SS.read_declarations()
    check('there are declarations', len(items) >= 5, str(len(items)))
    try:
        SS.validate_declarations(items)
        check('every declaration carries all six required fields', True)
    except SS.DeclarationError as exc:
        check('every declaration carries all six required fields', False,
              str(exc)[:200])
    check('each states what would turn it into a measurement',
          all((it.get('what_would_verify') or '').strip() for it in items))


def test_the_governance_declarations_are_present_and_standing():
    by_id = {d['id']: d for d in SS.read_declarations()}
    for want in ('REAL_MONEY_NOT_ENABLED', 'V2_NOT_EARNED',
                 'MARKET_IS_EVALUATION_ONLY', 'FANDUEL_PROVENANCE',
                 'EGRESS_DENIED'):
        check(f'{want} is declared and standing',
              by_id.get(want, {}).get('status') == 'STANDING',
              str(by_id.get(want, {}).get('status')))
    check('FanDuel provenance is still the relayed value, not upgraded',
          'VERIFIED_RULE_VALUE_RELAYED_SOURCE'
          in by_id['FANDUEL_PROVENANCE']['claim'],
          by_id['FANDUEL_PROVENANCE']['claim'][:120])
    check('and it still forbids inferring a salary from DraftKings',
          'DraftKings' in by_id['FANDUEL_PROVENANCE']['what_would_verify'])


def test_measured_and_declared_do_not_overlap():
    """A claim in both sections would be two truths again, which is the bug."""
    s = _live()
    ids = {d['id'] for d in s['declared']}
    check('no declaration id collides with a measured section name',
          not (ids & set(s['measured'])), str(ids & set(s['measured'])))


# ===================================================== honest non-measures

def test_an_unmeasurable_thing_is_recorded_as_such_and_not_as_a_zero():
    u = SS._unmeasured('the artifact is absent')
    check('an unmeasured value carries the NOT_MEASURED state',
          u['state'] == SS.NOT_MEASURED and u['why'], str(u))
    live = _live()['measured']
    for name, sec in live.items():
        if isinstance(sec, dict) and sec.get('state') == SS.NOT_MEASURED:
            check(f'{name} says why it is unmeasured',
                  bool((sec.get('why') or '').strip()), name)


def test_a_suite_total_carries_the_commit_it_was_measured_at():
    """A stale measurement presented as current is the defect being repaired."""
    su = _live()['measured']['suite']
    if su.get('state') == SS.NOT_MEASURED:
        check('the suite section explains its absence', bool(su.get('why')))
        return
    check('the suite total names the commit it was taken at',
          su['measured_at_commit'] and su['measured_at_commit'] != '',
          str(su['measured_at_commit']))
    check('and says whether that commit is HEAD',
          isinstance(su['is_current_head'], bool))
    check('and carries a staleness note either way',
          bool(su['staleness_note']), su['staleness_note'][:80])
    check('a NEWLY_INTRODUCED item is carried, never summarised away',
          'newly_introduced' in su)


def test_the_superseded_hand_written_state_is_preserved_unedited():
    """A correction creates a successor; it does not rewrite history."""
    sup = _live()['measured']['superseded_state_files']
    check('the hand-written state file is archived', len(sup) >= 1, str(sup))
    if not sup:
        return
    p = pathlib.Path(_ROOT) / sup[0]['path']
    check('the archived file is on disk', p.exists(), str(p))
    txt = p.read_text()
    check('it is kept unedited, with no supersession note prepended',
          not txt.lstrip().startswith('> SUPERSEDED')
          and 'Generated by' not in txt.split('\n')[0],
          txt.split('\n')[0][:80])
    check('and the successor points at it by path and hash',
          sup[0]['sha256'] and sup[0]['bytes'] > 0, str(sup[0]))
