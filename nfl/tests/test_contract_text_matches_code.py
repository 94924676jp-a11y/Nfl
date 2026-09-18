"""P8: a contract's prose and its executable constant must agree.

THE INCIDENT THIS FILE IS THE GUARD FOR

On 2026-09-17 at 14:25:34Z, commit `14a5257` created the Contract 4
pre-declaration stating that a quantity CLEARS when `a >= 0.90` -- "at least
18 of 20 batches agree" -- and asserting, in the same sentence, that 0.90 was
"the same 18-of-20 agreement its `BATCH_AGREEMENT` constant already uses".

It was not. `nfl/tools/draw_contract3.py` had read `BATCH_AGREEMENT = 19`
since `030b615` on 2026-09-16 at 18:30:24Z, and `draw_contract2.py` since
`b390fa0` earlier the same day. The pre-declaration relaxed a standing 0.95 to
0.90 while claiming it was not a change.

It was found by external review and corrected at `340d581`, 2026-09-17
15:45:33Z -- eighty minutes later, and BEFORE Contract 4 had run once, so no
result was reinterpreted. The correction was appended: the original wording is
quoted inside the document rather than deleted.

WHAT WAS STILL MISSING, AND IS THE ONLY NEW THING HERE

Nothing stopped it happening again. The correction fixed one number in one
document; it added no check. Eighty minutes was luck -- an external reviewer
happened to read that paragraph. This file is the check: every threshold a
contract document states in prose is compared against the constant the code
actually tests, and a disagreement fails.

WHAT THIS FILE DOES NOT DO

It does not decide which side is right. A disagreement is reported as a
disagreement with both values named; repairing it is a governed decision, and
the review that raised this said so in as many words: the executable threshold
must NOT be silently changed to match prose, nor prose silently changed to
match code.
"""
from __future__ import annotations

import os
import pathlib
import re
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

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


# A superseded passage is marked, not guessed at. The alternative -- deciding
# by heuristic whether a sentence is live prose or a quotation of withdrawn
# prose -- is how a real disagreement gets excused as "that's just the quote".
SUPERSEDED = re.compile(
    r'<!--\s*SUPERSEDED-BEGIN.*?-->.*?<!--\s*SUPERSEDED-END\s*-->',
    re.DOTALL)

#: (document, module, what the prose must agree with).
#: Adding a contract document means adding a line here. That is the mechanism.
CONTRACTS = (
    {'doc': 'nfl/production/DRAW_COUNT_CONTRACT_2.md',
     'module': 'nfl.tools.draw_contract2',
     'agreement': 'BATCH_AGREEMENT', 'batches': 'N_BATCHES'},
    {'doc': 'nfl/production/DRAW_COUNT_CONTRACT_3.md',
     'module': 'nfl.tools.draw_contract3',
     'agreement': 'BATCH_AGREEMENT', 'batches': 'N_BATCHES'},
    {'doc': 'nfl/research/contract4/DIAGNOSIS_AND_PREDECLARATION.md',
     'module': 'nfl.tools.draw_contract3',
     'agreement': 'BATCH_AGREEMENT', 'batches': 'N_BATCHES'},
)

#: "at least 19 of 20 batches", "19 of\n  20 non-overlapping batches".
N_OF_M = re.compile(r'(\d+)\s+of\s+(\d+)[^.\n]{0,40}batch', re.IGNORECASE)
#: "a >= 0.95"
RATIO = re.compile(r'a\s*>=\s*(0\.\d+)')


def live_text(path: pathlib.Path) -> str:
    return SUPERSEDED.sub(' ', path.read_text())


def _const(modname, name):
    mod = __import__(modname, fromlist=[name])
    return getattr(mod, name)


def test_contract_text_and_executable_constant_must_agree():
    for c in CONTRACTS:
        p = pathlib.Path(_ROOT) / c['doc']
        if not check(f'{c["doc"]} exists', p.exists(), str(p)):
            continue
        agree = _const(c['module'], c['agreement'])
        batches = _const(c['module'], c['batches'])
        txt = live_text(p)
        pairs = [(int(a), int(b)) for a, b in N_OF_M.findall(txt)]
        check(f'{c["doc"]} states its batch agreement in prose at all',
              bool(pairs), 'no "N of M batches" statement found')
        bad = [(a, b) for a, b in pairs if (a, b) != (agree, batches)]
        check(f'{c["doc"]}: every live "N of M batches" equals '
              f'{c["module"]}.{c["agreement"]}={agree} of '
              f'{c["batches"]}={batches}',
              not bad, f'disagreeing statements: {bad}')
        ratios = [float(r) for r in RATIO.findall(txt)]
        want = agree / batches
        badr = [r for r in ratios if abs(r - want) > 1e-9]
        check(f'{c["doc"]}: every live "a >= x" equals {want}',
              not badr, f'disagreeing ratios: {badr} against {want}')


def test_the_code_actually_tests_against_the_constant():
    """A constant nothing compares against is decoration, not a threshold."""
    for mod, path in (('draw_contract2', 'nfl/tools/draw_contract2.py'),
                      ('draw_contract3', 'nfl/tools/draw_contract3.py')):
        src = (pathlib.Path(_ROOT) / path).read_text()
        check(f'{path} compares against BATCH_AGREEMENT rather than a literal',
              're.search' not in src and '>= BATCH_AGREEMENT' in src,
              'no `>= BATCH_AGREEMENT` comparison found')
        lits = re.findall(r'n_mode\s*>=\s*(\d+)', src)
        check(f'{path} hard-codes no agreement literal beside the constant',
              not lits, str(lits))


def test_the_two_contract_modules_do_not_disagree_with_each_other():
    a2 = _const('nfl.tools.draw_contract2', 'BATCH_AGREEMENT')
    a3 = _const('nfl.tools.draw_contract3', 'BATCH_AGREEMENT')
    b2 = _const('nfl.tools.draw_contract2', 'N_BATCHES')
    b3 = _const('nfl.tools.draw_contract3', 'N_BATCHES')
    check('contract 2 and contract 3 agree on the batch count', b2 == b3,
          f'{b2} vs {b3}')
    check('contract 2 and contract 3 agree on the agreement threshold',
          a2 == a3, f'{a2} vs {a3}')


def test_the_superseded_wording_is_still_in_the_document():
    """The correction was append-only. Deleting the old text would erase the
    only record of what the gate briefly said."""
    p = (pathlib.Path(_ROOT)
         / 'nfl/research/contract4/DIAGNOSIS_AND_PREDECLARATION.md')
    raw = p.read_text()
    check('the withdrawn 18-of-20 wording is preserved verbatim',
          '18 of 20 batches agree' in raw)
    check('and it is inside a marked superseded block',
          '18 of 20 batches agree' not in live_text(p),
          'the withdrawn wording is not enclosed by SUPERSEDED markers')
    check('the correction names when it was made',
          '2026-09-17' in raw)
    check('and that it was made before the contract ran',
          'BEFORE THIS CONTRACT HAS RUN' in raw)
    check('the document forbids reusing 18 of 20 as precedent',
          'must be argued on its own' in raw)


def test_the_marker_convention_is_not_load_bearing_for_the_reader():
    """The markers are HTML comments: they change no rendered word.

    This matters because the alternative -- editing the quoted passage to make
    it machine-distinguishable -- would have altered the historical text, which
    is the thing the append-only rule exists to prevent.
    """
    p = (pathlib.Path(_ROOT)
         / 'nfl/research/contract4/DIAGNOSIS_AND_PREDECLARATION.md')
    raw = p.read_text()
    marks = re.findall(r'<!--\s*SUPERSEDED-(BEGIN|END).*?-->', raw)
    check('the superseded region is delimited by a begin and an end',
          marks.count('BEGIN') == marks.count('END') >= 1, str(marks))
    check('every marker is an HTML comment, so nothing rendered changes',
          all(m.startswith('<!--') and m.endswith('-->')
              for m in re.findall(r'<!--\s*SUPERSEDED-\w+.*?-->', raw)))
    check('a BEGIN marker states why the passage is superseded',
          all(len(r.strip()) > 4 for r in
              re.findall(r'<!--\s*SUPERSEDED-BEGIN\s*(.*?)\s*-->', raw)),
          str(re.findall(r'<!--\s*SUPERSEDED-BEGIN\s*(.*?)\s*-->', raw)))


def test_the_detector_fires_on_a_real_disagreement():
    """A guard that has never been shown to fire is not a guard.

    This is the negative control the 2026-09-17 correction did not have. It
    rebuilds the exact defect -- a document claiming 18 of 20 and `a >= 0.90`
    against constants of 19 and 20 -- and requires the extraction to report it.
    """
    import tempfile
    d = tempfile.mkdtemp(prefix='contract_')
    p = pathlib.Path(d) / 'BAD.md'
    p.write_text(
        'The quantity CLEARS when `a >= 0.90` -- at least 18 of 20 batches\n'
        'agree on the same integer.\n')
    txt = live_text(p)
    pairs = [(int(a), int(b)) for a, b in N_OF_M.findall(txt)]
    ratios = [float(r) for r in RATIO.findall(txt)]
    check('the "N of M batches" extraction finds the defect wording',
          (18, 20) in pairs, str(pairs))
    check('the ratio extraction finds 0.90', 0.90 in ratios, str(ratios))
    check('and both disagree with the standing constants 19 of 20',
          (18, 20) != (19, 20) and abs(0.90 - 19 / 20) > 1e-9)

    good = pathlib.Path(d) / 'GOOD.md'
    good.write_text('CLEARS when `a >= 0.95` -- at least 19 of 20 batches\n'
                    'agree.\n')
    gt = live_text(good)
    check('a conforming document produces no disagreement',
          [(int(a), int(b)) for a, b in N_OF_M.findall(gt)] == [(19, 20)]
          and [float(r) for r in RATIO.findall(gt)] == [0.95])


def test_a_superseded_block_hides_its_contents_and_nothing_else():
    """The exemption must be narrow, or it becomes a way to hide live prose."""
    import tempfile
    d = tempfile.mkdtemp(prefix='contract_')
    p = pathlib.Path(d) / 'MIXED.md'
    p.write_text(
        'Live: at least 19 of 20 batches agree.\n'
        '<!-- SUPERSEDED-BEGIN withdrawn -->\n'
        'Old: at least 18 of 20 batches agree.\n'
        '<!-- SUPERSEDED-END -->\n'
        'Also live: at least 17 of 20 batches agree.\n')
    txt = live_text(p)
    pairs = [(int(a), int(b)) for a, b in N_OF_M.findall(txt)]
    check('the superseded statement is removed from the live text',
          (18, 20) not in pairs, str(pairs))
    check('the live statement before it survives', (19, 20) in pairs,
          str(pairs))
    check('and a live statement AFTER it survives too -- the block does not '
          'swallow the rest of the document', (17, 20) in pairs, str(pairs))
    check('so a second disagreement past the block would still fail',
          (17, 20) in pairs and (17, 20) != (19, 20))
