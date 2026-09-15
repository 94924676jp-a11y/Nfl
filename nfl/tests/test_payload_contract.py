"""D22. Every content kind gets the D20 question, with both controls.

THE AUDIT THIS FILE IS THE RESULT OF

D20 proved that keyword presence is not substance. The obvious next question is
whether the OTHER content kinds have the same hole, and they do -- both of them,
for the same reason: the check counts the ENVELOPE.

  json  ESPN's injuries document is {injuries:[32 teams], season, status,
        timestamp}. The old check scores len-of-lists plus one per scalar, so
        32 + 3 = 35, against 800 real injury entries. EMPTY EVERY TEAM'S LIST
        AND IT STILL SCORES 35 -- indistinguishable from a healthy document.
        Drop the injuries key and the three scalars alone score 3, which passes.

  csv   The old check is len(nonblank lines) - 1. It counts rows and never
        looks at a column, which is exactly the defect this project already
        shipped once: an export of 7,926 rows with every meaningful column
        blank, because the field names were guessed rather than read.

THE BINDING TEST STANDARD (Owner Directive 3 section 8): a guard is not
demonstrated by compliant data passing it. So every section here carries BOTH
controls -- the real committed blobs must still pass, and a seeded violation
must fire -- and section E strips the declaration to show the guard is what is
doing the work rather than something else.

WHAT IS DELIBERATELY NOT DONE HERE. No column was chosen to make the corpus
pass. `report_status` is blank on every row of two committed injuries blobs
(bfa4aa0ee7cde902 and 1bf460ad261559a8, 2026-09-07/08) because the game-status
designation is not assigned until the final report -- a CORRECT empty on a
midweek practice report. Requiring it outright would have flipped two
legitimate captures to DEFERRED; quietly dropping it because it failed would be
fitting the guard to the data. Hence `substantive_any_of`, which asks that the
row say SOMETHING about availability without dictating which week it is.

Run standalone:  python3.12 nfl/tests/test_payload_contract.py
"""
import copy
import dataclasses
import gzip
import json
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from nfl.capture import payload_contract as PC                     # noqa: E402
from nfl.capture import registry as reg                            # noqa: E402

PASSED = FAILED = 0
NOT_EXECUTED = []
ROOT = pathlib.Path(__file__).resolve().parents[2]
VINTAGE = ROOT / 'nfl' / 'vintage'


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


def _blobs(name, ext):
    return sorted(VINTAGE.glob(f'{name}.*.{ext}.gz'))


def _text(p):
    return gzip.decompress(p.read_bytes()).decode('utf-8', 'replace')


# --------------------------------------------------------------------------
def test_a_every_source_that_can_declare_a_contract_has_one():
    """A CONTRACT IS READ FROM A SCHEMA, NEVER GUESSED.

    So this splits two facts that look alike. A source with committed blobs and
    no contract is a FAILURE -- the schema is sitting right there. A source with
    NO blob has nothing to read a contract from, and inventing plausible column
    names for it would be the 7,926-row defect committed on purpose. That is
    NOT_EXECUTED, which is not a pass, and it names what would discharge it.
    """
    print('\nA. the contract surface')
    field = {'html': 'row_container', 'json': 'payload_path',
             'csv': 'required_columns'}
    ext = {'html': 'html', 'json': 'json', 'csv': 'csv'}
    for s in reg.REGISTRY:
        kind = getattr(s, 'content_kind', None)
        if kind not in field:
            continue
        declared = bool(getattr(s, field[kind], ()))
        has_blob = bool(_blobs(s.name, ext[kind]))
        if declared:
            check(f'  {s.name} ({kind}) declares {field[kind]}', True)
        elif has_blob:
            check(f'  {s.name} ({kind}) declares {field[kind]}', False,
                  'blobs exist, so the schema is available and there is no '
                  'excuse for an undeclared contract')
        else:
            not_executed(
                f'  {s.name} ({kind}) has no {field[kind]}',
                f'zero committed blobs, so the schema cannot be READ. '
                f'reachability={s.reachability.name}, '
                f'watch_only={getattr(s, "watch_only", False)}. Declaring '
                f'guessed column names here would be the defect this file '
                f'exists to prevent. Discharged by one captured sample; '
                f'requested as OUT-017.')


def test_b_positive_control_every_committed_blob_still_passes():
    """The half that protects real data. Nothing healthy may be refused."""
    print('\nB. POSITIVE CONTROL -- healthy sources keep passing')
    expect_refused = {'official_inactives'}
    for s in reg.REGISTRY:
        kind = getattr(s, 'content_kind', None)
        ext = {'csv': 'csv', 'json': 'json', 'html': 'html'}.get(kind)
        if not ext:
            continue
        hits = _blobs(s.name, ext)
        if not hits:
            not_executed(f'  {s.name}', 'no committed blobs to check')
            continue
        bad = []
        for p in hits:
            t = _text(p)
            if kind == 'json':
                ok, code, _ = PC.check_json(json.loads(t), s)
            elif kind == 'csv':
                ok, code, _ = PC.check_csv(t, s)
            else:
                ok, code, _ = PC.check_html(t, s)
            if not ok:
                bad.append((p.name, code))
        if s.name in expect_refused:
            check(f'  {s.name}: all {len(hits)} refused, as D20 requires',
                  len(bad) == len(hits), f'{len(bad)} of {len(hits)}')
        else:
            check(f'  {s.name}: all {len(hits)} still pass',
                  not bad, str(bad[:3]))


def test_c_negative_control_json_the_envelope_is_not_the_payload():
    """D22's core. Seeded emptiness that the OLD check cannot see."""
    print('\nC. NEGATIVE CONTROL -- json')
    spec = reg.BY_NAME['espn_injuries_json']
    hits = _blobs('espn_injuries_json', 'json')
    if not hits:
        not_executed('no espn blob', 'cannot seed without a real document')
        return
    doc = json.loads(_text(hits[0]))

    def old(d):
        """Transcribed from the pre-D22 json branch."""
        return (len(d) if isinstance(d, list)
                else sum(len(v) if isinstance(v, list) else 1
                         for v in d.values()) if isinstance(d, dict) else 0)

    ok, _, ev = PC.check_json(doc, spec)
    check('a healthy document passes', ok, str(ev))
    check('  and the contract counts ENTITIES, not the envelope',
          ev['n_entities'] > old(doc) * 10,
          f"entities={ev['n_entities']} vs old envelope count={old(doc)}")

    # 1. every team kept, every team's injury list emptied.
    c1 = copy.deepcopy(doc)
    removed = 0
    for team in c1.get('injuries', []):
        for k, v in list(team.items()):
            if isinstance(v, list):
                removed += len(v)
                team[k] = []
    ok1, code1, ev1 = PC.check_json(c1, spec)
    check(f'  {removed} injury entries removed, 32 teams kept: REFUSED',
          (not ok1) and code1 == PC.CODE_EMPTY, f'{code1} {ev1}')
    check('    and this is the case the old check could NOT see',
          old(c1) == old(doc),
          f'old scores {old(c1)} vs {old(doc)} -- if these differ the old '
          f'check would have caught it and this control is not the D22 shape')

    # 2. the injuries key emptied entirely.
    c2 = copy.deepcopy(doc)
    c2['injuries'] = []
    ok2, code2, _ = PC.check_json(c2, spec)
    check('  injuries list emptied entirely: REFUSED',
          (not ok2) and code2 == PC.CODE_EMPTY, str(code2))
    check('    and the old check passed it on the scalars alone',
          old(c2) >= 1, f'old scores {old(c2)}')

    # 3. envelope only.
    c3 = {k: v for k, v in doc.items() if k != 'injuries'}
    ok3, code3, _ = PC.check_json(c3, spec)
    check('  envelope with no injuries key at all: REFUSED',
          (not ok3) and code3 == PC.CODE_EMPTY, str(code3))


def test_d_negative_control_csv_a_header_is_a_promise():
    print('\nD. NEGATIVE CONTROL -- csv')
    spec = reg.BY_NAME['depth_charts']
    hits = _blobs('depth_charts', 'csv')
    if not hits:
        not_executed('no depth_charts blob', 'cannot seed without a real file')
        return
    t = _text(hits[-1])
    lines = [ln for ln in t.splitlines() if ln.strip()]
    header = lines[0]
    cols = [c.strip() for c in header.split(',')]

    ok, _, ev = PC.check_csv(t, spec)
    check('a healthy csv passes', ok, str(ev))

    # 1. rows present, a required column blanked in every one of them.
    i = cols.index('gsis_id')
    blanked = [header]
    for ln in lines[1:]:
        parts = ln.split(',')
        if len(parts) > i:
            parts[i] = ''
        blanked.append(','.join(parts))
    ok1, code1, ev1 = PC.check_csv('\n'.join(blanked), spec)
    check(f'  {len(lines)-1} rows kept, gsis_id blanked in every one: REFUSED',
          (not ok1) and code1 == 'SCHEMA_COLUMNS_PRESENT_BUT_EMPTY',
          f'{code1} {ev1}')
    check('    and the old row count would have passed it',
          len(blanked) - 1 >= 1, f'{len(blanked)-1} rows')

    # 2. the column gone from the header -- a DIFFERENT fact, named differently.
    keep = [j for j, c in enumerate(cols) if c != 'gsis_id']
    dropped = [','.join([c for j, c in enumerate(cols) if j in keep])]
    for ln in lines[1:]:
        parts = ln.split(',')
        dropped.append(','.join([p for j, p in enumerate(parts) if j in keep]))
    ok2, code2, _ = PC.check_csv('\n'.join(dropped), spec)
    check('  gsis_id absent from the header: REFUSED, and named separately',
          (not ok2) and code2 == 'SCHEMA_COLUMNS_ABSENT', str(code2))
    check('    absent and blank are not the same code',
          code1 != code2, f'{code1} vs {code2}')

    # 3. the any-of contract: identity intact, substance gone.
    inj = reg.BY_NAME['injuries']
    ih = _blobs('injuries', 'csv')
    if not ih:
        not_executed('  no injuries blob', 'cannot exercise substantive_any_of')
        return
    it = _text(ih[-1])
    il = [ln for ln in it.splitlines() if ln.strip()]
    ic = [c.strip() for c in il[0].split(',')]
    ok3, _, ev3 = PC.check_csv(it, inj)
    check('  a real injuries csv passes', ok3, str(ev3))
    idx = [ic.index(c) for c in inj.substantive_any_of if c in ic]
    stripped = [il[0]]
    for ln in il[1:]:
        parts = ln.split(',')
        for j in idx:
            if len(parts) > j:
                parts[j] = ''
        stripped.append(','.join(parts))
    ok4, code4, ev4 = PC.check_csv('\n'.join(stripped), inj)
    check('  identity intact but EVERY availability column blanked: REFUSED',
          (not ok4) and code4 == PC.CODE_EMPTY, f'{code4} {ev4}')


def test_e_the_contracts_are_load_bearing():
    """Strip the declaration and the seeded violation must pass again."""
    print('\nE. bypass -- the declarations are what is doing the work')
    spec = reg.BY_NAME['espn_injuries_json']
    hits = _blobs('espn_injuries_json', 'json')
    if not hits:
        not_executed('no espn blob', 'nothing to bypass against')
        return
    doc = json.loads(_text(hits[0]))
    empty = copy.deepcopy(doc)
    empty['injuries'] = []
    live_ok, _, _ = PC.check_json(empty, spec)
    stub_ok, _, _ = PC.check_json(empty,
                                  dataclasses.replace(spec, payload_path=()))
    check('with payload_path declared, the empty document is refused',
          not live_ok)
    check('with it stripped, the same document passes again',
          stub_ok,
          'if this is not True the refusal came from somewhere else and this '
          'test proves nothing about payload_path')

    csvspec = reg.BY_NAME['depth_charts']
    ch = _blobs('depth_charts', 'csv')
    if not ch:
        not_executed('  no depth_charts blob', 'nothing to bypass against')
        return
    t = _text(ch[-1])
    lines = [ln for ln in t.splitlines() if ln.strip()]
    cols = [c.strip() for c in lines[0].split(',')]
    i = cols.index('gsis_id')
    blanked = [lines[0]]
    for ln in lines[1:]:
        parts = ln.split(',')
        if len(parts) > i:
            parts[i] = ''
        blanked.append(','.join(parts))
    body = '\n'.join(blanked)
    check('  with required_columns declared, the blanked csv is refused',
          not PC.check_csv(body, csvspec)[0])
    check('  with them stripped, it passes again',
          PC.check_csv(body, dataclasses.replace(
              csvspec, required_columns=(), substantive_any_of=()))[0])


def test_f_an_undeclared_source_is_unaffected():
    """Safe to adopt incrementally, and that must be demonstrated not assumed."""
    print('\nF. a source that declares nothing keeps its old behaviour')
    bare = dataclasses.replace(reg.BY_NAME['depth_charts'],
                               required_columns=(), substantive_any_of=())
    ok, code, ev = PC.check_csv('a,b,c\n,,\n', bare)
    check('an undeclared csv source is not refused', ok, f'{code} {ev}')
    barej = dataclasses.replace(reg.BY_NAME['espn_injuries_json'],
                                payload_path=())
    ok2, code2, _ = PC.check_json({'anything': []}, barej)
    check('an undeclared json source is not refused', ok2, str(code2))


if __name__ == '__main__':
    test_a_every_source_that_can_declare_a_contract_has_one()
    test_b_positive_control_every_committed_blob_still_passes()
    test_c_negative_control_json_the_envelope_is_not_the_payload()
    test_d_negative_control_csv_a_header_is_a_promise()
    test_e_the_contracts_are_load_bearing()
    test_f_an_undeclared_source_is_unaffected()
    print(f'\n{PASSED} passed, {FAILED} failed, {len(NOT_EXECUTED)} NOT_EXECUTED')
    for label, why in NOT_EXECUTED:
        print(f'  NOT_EXECUTED: {label} -- {why}')
    sys.exit(1 if FAILED else 0)
