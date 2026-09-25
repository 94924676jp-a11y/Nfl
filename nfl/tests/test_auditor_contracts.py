"""An auditor is not trustworthy because auditing is its purpose.

Three separate tools in this repository counted their own file as a finding:
`discovery_audit` reported six of its own references, `cross_layer_audit` needed
the same exclusion, and `manifest_consumer_census` listed itself among the
modules that would need editing to shard the manifest. Each time it was caught
by reading the output, which is luck dressed as diligence.

Owner ruling 2026-09-25: audit tooling needs adversarial contracts of its own.
This is the first of them. An auditor whose subject is the repository is inside
its own subject, and the inflation is always in the direction that makes the
problem look bigger, which is the direction nobody questions.
"""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

PASSED = 0
FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


def test_A_no_auditor_reports_its_own_file():
    print('\nA. the third occurrence became a rule')
    from nfl.tools import manifest_consumer_census as MC
    own = 'nfl/tools/manifest_consumer_census.py'
    check('manifest_consumer_census excludes itself', own not in MC.census(),
          [k for k in MC.census() if 'census' in k])

    from nfl.production import discovery_audit as DA
    rep = DA.scan()
    files = rep.get('files') or {}
    check('discovery_audit excludes itself',
          not any('discovery_audit' in f for f in files),
          [f for f in files if 'discovery_audit' in f])


def test_B_a_self_counting_auditor_would_be_visible():
    print('\nB. the test can actually fail')
    from nfl.tools import manifest_consumer_census as MC
    src = pathlib.Path(_REPO / 'nfl/tools/manifest_consumer_census.py'
                       ).read_text()
    check('the exclusion is explicit in the source, not incidental',
          'EXCLUDE SELF' in src or '__file__' in src)
    check('and the needle it scans for really is in its own file',
          MC.NEEDLE in src,
          'if this fails the exclusion is untested because there is nothing '
          'to exclude')


#: Auditors must carry this literal marker in their module docstring.
#:
#: The first version of this test matched on phrases like "heuristic" and "is a
#: question". It failed cross_layer_audit.py, which DOES state its limits, in
#: the words "a question that must be answered in writing, not a bug" -- so the
#: test was wrong, not the module. Matching prose tests the wording rather than
#: the property. An explicit greppable marker is a contract; a phrase list is a
#: guess about how somebody will phrase it.
LIMITS_MARKER = 'LIMITS'

AUDITORS = (
    'nfl/tools/cross_layer_audit.py',
    'nfl/tools/manifest_consumer_census.py',
    'nfl/tools/source_rowcount_census.py',
    'nfl/production/discovery_audit.py',
)


def test_C_every_auditor_declares_what_it_does_not_know():
    print('\nC. a heuristic that does not say so reads as a measurement')
    for rel in AUDITORS:
        src = pathlib.Path(_REPO / rel).read_text()
        check(f'{rel.split("/")[-1]} carries the LIMITS marker',
              LIMITS_MARKER in src,
              'add a LIMITS section to the module docstring saying what this '
              'tool does not establish')


def test_D_the_marker_is_in_the_docstring_not_a_comment():
    print('\nD. a contract satisfied by a stray word is not one')
    import ast
    for rel in AUDITORS:
        mod = ast.parse(pathlib.Path(_REPO / rel).read_text())
        doc = ast.get_docstring(mod) or ''
        check(f'{rel.split("/")[-1]} states it in the module docstring',
              LIMITS_MARKER in doc,
              'the marker exists somewhere in the file but not where a reader '
              'of help() would find it')
