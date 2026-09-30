#!/usr/bin/env python3.12
"""Every failing suite carries a CATEGORY and evidence, or the taxonomy refuses.

WHY. "47 modules failing" tells a reader almost nothing about product readiness. A test red because
an external service is absent, a test red because it encodes an architecture we replaced, and a test
red because the product is broken are three completely different facts, and a single count renders
them identically. That is the same class of defect as a single scalar over a prior that is two
objects: the number is not wrong, it is unreadable.

So a failing module is not allowed to be merely counted. It is classified, the classification names
the evidence, and a module with no classification reads UNCLASSIFIED -- which is a DEBT, reported as
such, never folded into a pass and never silently tolerated as "known red".

THE CATEGORIES ARE NOT INTERCHANGEABLE and the boundary that matters most is the first one:

  REAL_PRODUCT_DEFECT   the product does the wrong thing. This is the only category that says the
                        system is broken, and it is the only one that should ever block a release.
  STALE_EXPECTATION     the test encodes an architecture the repository no longer has. The test is
                        wrong about today, not about then.
  ENVIRONMENT_DEPENDENCY needs data or a service this checkout does not hold. BLOCKED, not FAILED,
                        and it names what would resolve it.
  INTENTIONAL_BLOCKER   expected red until a declared dependency exists. Someone chose this.
  BAD_TEST              the test itself is wrong -- asserts the wrong thing, or asserts a number it
                        read off the implementation.
  ORDER_DEPENDENT       passes alone, fails in sequence. Says nothing about the product until fixed;
                        see REQUIRES_OWN_PROCESS in run_suite for the one legitimate sub-case.

WHAT THIS FILE IS NOT. It is not a way to make the suite green. Classifying a failure does not fix
it, and the artifact reports the REAL_PRODUCT_DEFECT count first and separately for exactly that
reason. A taxonomy that made a red suite feel resolved would be worse than no taxonomy.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

OUT = _REPO / 'nfl/production/suite/SUITE_TAXONOMY.json'
REGISTRY = _REPO / 'nfl/production/suite/CLASSIFICATIONS.json'

REAL_PRODUCT_DEFECT = 'REAL_PRODUCT_DEFECT'
STALE_EXPECTATION = 'STALE_EXPECTATION'
ENVIRONMENT_DEPENDENCY = 'ENVIRONMENT_DEPENDENCY'
INTENTIONAL_BLOCKER = 'INTENTIONAL_BLOCKER'
BAD_TEST = 'BAD_TEST'
ORDER_DEPENDENT = 'ORDER_DEPENDENT'
UNCLASSIFIED = 'UNCLASSIFIED'

CATEGORIES = (REAL_PRODUCT_DEFECT, STALE_EXPECTATION, ENVIRONMENT_DEPENDENCY,
              INTENTIONAL_BLOCKER, BAD_TEST, ORDER_DEPENDENT)

#: Only this one means the product is broken. Kept as its own name so a reader cannot lose it in a
#: total, and so a future edit that adds a category has to decide deliberately whether it blocks.
BLOCKING_CATEGORIES = (REAL_PRODUCT_DEFECT,)

#: THE MODULE KEY IS THE FULL REPO-RELATIVE PATH, not the basename. The runner discovers
#: `sportsplatform/**/test_*.py` as well as `nfl/tests/test_*.py`, and an earlier version of this
#: regex was anchored to `nfl/tests/`, so a failing sportsplatform module parsed as no module at all
#: and vanished from the taxonomy. That is principle 8 -- a test the harness does not count does not
#: exist -- reappearing one layer up, in the thing that reads the harness.
_TALLY_LINE = re.compile(
    r'((?:[\w.-]+/)*test_[a-z0-9_]+\.py)\s+\d+ fn, \d+ check\(s\), (\d+) failing')

#: A module declaring REQUIRES_OWN_PROCESS reports through a different line. It has to be read too,
#: or the four modules that carry that declaration -- the FantasyCruncher firewall family -- would be
#: unclassifiable by construction.
_OWN_PROCESS_LINE = re.compile(
    r'((?:[\w.-]+/)*test_[a-z0-9_]+\.py)\s+OWN PROCESS, \d+ check\(s\), (\d+) failing')

#: An isolated child whose tally could not be parsed is UNKNOWN, and unknown is not zero. The runner
#: already refuses to count it as a pass; this reader must not quietly restore it to one.
_OWN_PROCESS_UNREADABLE = re.compile(
    r'((?:[\w.-]+/)*test_[a-z0-9_]+\.py)\s+OWN PROCESS, tally unreadable')


def failing_from_log(path) -> Outcome:
    """The failing modules a run_suite log reports, with their failing-check counts."""
    p = pathlib.Path(path)
    if not p.exists():
        return Outcome.blocked('SUITE_LOG_ABSENT', f'{p} does not exist', cause=Cause.DATA)
    text = p.read_text(errors='replace')
    seen = {}
    for rx in (_TALLY_LINE, _OWN_PROCESS_LINE):
        for m in rx.finditer(text):
            seen[m.group(1)] = int(m.group(2))
    unreadable = sorted({m.group(1) for m in _OWN_PROCESS_UNREADABLE.finditer(text)})
    if unreadable:
        return Outcome.fail(
            'SUITE_LOG_HAS_UNREADABLE_TALLIES',
            f'{len(unreadable)} isolated module(s) produced no parsable tally, so their result is '
            f'UNKNOWN. Classifying the rest would report a failure count that silently excludes '
            f'them, which reads as though they passed.',
            unreadable=unreadable)
    if not seen:
        return Outcome.fail(
            'SUITE_LOG_UNPARSABLE',
            f'{p.name} yielded no module tallies. An empty parse of a suite log is an error, not a '
            f'suite with no failures.')
    failing = {k: v for k, v in seen.items() if v}
    return Outcome.ok('SUITE_LOG_READ', value={
        'log': str(p), 'n_modules_tallied': len(seen), 'n_failing': len(failing),
        'MODULE_KEY_IS': 'the repo-relative path, so two modules sharing a basename stay distinct',
        'failing': failing})


def load_registry() -> dict:
    if not REGISTRY.exists():
        return {}
    d = json.loads(REGISTRY.read_text())
    return d.get('classifications', d)


def classify(path) -> Outcome:
    """Join a suite log to the classification registry. UNCLASSIFIED is a debt, never a pass."""
    r = failing_from_log(path)
    if r.state.name != 'PASS':
        return r
    reg = load_registry()
    rows, counts, unclassified, bad_category = [], {}, [], []
    for mod, n in sorted(r.value['failing'].items()):
        c = reg.get(mod)
        if c is None:
            unclassified.append(mod)
            rows.append({'module': mod, 'failing_checks': n, 'category': UNCLASSIFIED,
                         'evidence': None})
            counts[UNCLASSIFIED] = counts.get(UNCLASSIFIED, 0) + 1
            continue
        cat = c.get('category')
        if cat not in CATEGORIES:
            bad_category.append({'module': mod, 'category': cat})
            continue
        if not (c.get('evidence') or '').strip():
            bad_category.append({'module': mod, 'category': cat, 'why': 'NO_EVIDENCE'})
            continue
        rows.append({'module': mod, 'failing_checks': n, 'category': cat,
                     'evidence': c['evidence'], 'classified_on': c.get('classified_on')})
        counts[cat] = counts.get(cat, 0) + 1

    if bad_category:
        return Outcome.fail(
            'CLASSIFICATION_INVALID',
            f'{len(bad_category)} classification(s) name a category outside the vocabulary or carry '
            f'no evidence. A category with no evidence is an opinion, and the point of the taxonomy '
            f'is that it is not one.',
            vocabulary=list(CATEGORIES), offending=bad_category[:8])

    blocking = sum(counts.get(c, 0) for c in BLOCKING_CATEGORIES)
    art = {
        'ARTIFACT': 'SUITE_TAXONOMY',
        'WHAT_A_COUNT_DOES_NOT_TELL_YOU': (
            'a test red because a service is absent, a test red because it encodes a replaced '
            'architecture, and a test red because the product is broken are three different facts. '
            'A single failing count renders them identically, which is why this artifact reports '
            'the blocking category separately and first.'),
        'source_log': r.value['log'],
        'n_modules_tallied': r.value['n_modules_tallied'],
        'n_failing_modules': r.value['n_failing'],
        'n_blocking_modules': blocking,
        'BLOCKING_MEANS': (f'{list(BLOCKING_CATEGORIES)} only. Every other category is a real '
                           f'outstanding item and none of them says the product does the wrong '
                           f'thing.'),
        'by_category': dict(sorted(counts.items())),
        'unclassified': unclassified,
        'UNCLASSIFIED_IS_A_DEBT': (
            'a failing module with no classification is reported here and is NOT counted as '
            'non-blocking. Absence of a judgement is not a judgement of harmless.'),
        'NOT_A_WAY_TO_GO_GREEN': (
            'classifying a failure does not fix it. PROJECTION_SYSTEM_STATE is untouched by this '
            'artifact and no category clears a red suite.'),
        'modules': rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(art, indent=2))
    if unclassified:
        return Outcome.deferred(
            'SUITE_FAILURES_PARTLY_UNCLASSIFIED',
            f'{len(unclassified)} of {r.value["n_failing"]} failing modules have no classification',
            owed='classify each remaining module with a category and cited evidence',
            unclassified=unclassified[:12], by_category=dict(sorted(counts.items())),
            n_blocking=blocking)
    return Outcome.ok('SUITE_FAILURES_CLASSIFIED', value={
        'n_failing': r.value['n_failing'], 'n_blocking': blocking,
        'by_category': dict(sorted(counts.items()))})


def main() -> int:
    log = sys.argv[1] if len(sys.argv) > 1 else None
    if not log:
        print('usage: taxonomy.py <run_suite log>')
        return 2
    o = classify(log)
    print(o.state, o.code)
    print(o.detail or '')
    print(json.dumps(o.value if o.state.name == 'PASS' else o.evidence, indent=2, default=str))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
