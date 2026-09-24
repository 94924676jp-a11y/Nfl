"""Seven axes that must not collapse into one light.

WHAT THIS MODULE ASSERTS
========================
1. NOT_ESTABLISHED IS THE DEFAULT AND IS NOT A PASS. A source starts having
   proved nothing. An axis nobody measured must never read PASS, because the
   whole failure this project is organised against is an unmeasured thing
   read as a measured one.
2. THE AXIS SET IS CLOSED. An undeclared axis raises rather than appearing, so
   a source cannot quietly grow a dimension nobody agreed to.
3. TRANSPORT AND CONTENT ARE INDEPENDENT. The NFL.com landing page is the
   worked case: 402 PASS rows recorded, 363 of 367 blobs carrying the page's
   own "check back soon" text. Transport PASS, content FAIL, and the pair must
   be expressible.
4. RESTRICTED IS PURPOSE-SCOPED, NOT A POLITE FAIL. ESPN is authorised to
   answer "is this player listed OUT" and refused for "who is officially
   inactive". If RESTRICTED failed every purpose it would be FAIL with a nicer
   name and the axis would have collapsed again.
5. A POSITIVE OBSERVATION FROM A TRUNCATED FEED IS USABLE; A NEGATIVE
   INFERENCE FROM IT IS NOT. This is the completeness axis earning its place:
   the same feed answers "he is listed OUT" and must refuse "he is not hurt".
6. THERE IS NO TRUTH AXIS, deliberately. Nothing here claims a source is
   right, and a report implying it would be the most dangerous green light of
   all.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.production import source_validity as SV  # noqa: E402

PASSED = FAILED = BLOCKED = 0


def chk(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def test_not_established_is_the_default_and_is_not_a_pass():
    r = SV.new_report('anything')
    chk('every axis defaults to NOT_ESTABLISHED',
        all(r['axes'][a]['state'] == SV.NOT_ESTABLISHED
            for a in SV.AXIS_NAMES))
    u = SV.usable_for(r, 'any purpose')
    chk('and a wholly unmeasured source is not usable', not u['usable'])
    chk('with every axis named as failing',
        sorted(u['failing_axes']) == sorted(SV.AXIS_NAMES))


def test_the_axis_set_is_closed():
    try:
        SV.new_report('x', plausibility=SV.PASS)
        chk('an undeclared axis raises', False, 'it was accepted')
    except SV.ValidityError as e:
        chk('an undeclared axis raises', 'not declared axes' in str(e))
    try:
        SV.new_report('x', transport='VIBES')
        chk('an undeclared state raises', False, 'it was accepted')
    except SV.ValidityError as e:
        chk('an undeclared state raises', 'not one of the declared' in str(e))
    try:
        SV.new_report('')
        chk('an unnamed source raises', False, 'it was accepted')
    except SV.ValidityError:
        chk('an unnamed source raises', True)
    chk('seven axes, no more', len(SV.AXIS_NAMES) == 7)
    chk('and no truth axis', 'truth' not in SV.AXIS_NAMES)


def test_transport_and_content_are_independent():
    r = SV.nfl_inactives_landing_report(empty_state=True)
    chk('transport passes', r['axes']['transport']['state'] == SV.PASS)
    chk('content fails', r['axes']['content']['state'] == SV.FAIL)
    chk('and the detail quotes the page against itself',
        'check back soon' in r['axes']['content']['detail'])
    u = SV.usable_for(r, 'who is officially inactive',
                      requires=('transport', 'content'))
    chk('so it cannot answer the question it is authorised for',
        not u['usable'] and u['failing_axes'].get('content') == SV.FAIL)
    ok = SV.nfl_inactives_landing_report(empty_state=False)
    chk('a populated capture passes content',
        ok['axes']['content']['state'] == SV.PASS)


def test_restricted_is_purpose_scoped_not_a_polite_fail():
    e = SV.espn_injuries_report(truncated=True, n_clubs=32,
                                n_clubs_at_cap=32, consumed=True)
    chk('eligibility is RESTRICTED',
        e['axes']['eligibility']['state'] == SV.RESTRICTED)
    listed = SV.usable_for(e, 'is this player listed OUT',
                           requires=('transport', 'content', 'attribution',
                                     'eligibility'))
    chk('ESPN MAY answer "is this player listed OUT"', listed['usable'],
        listed['detail'])
    inactive = SV.usable_for(e, 'who is officially inactive',
                             requires=('transport', 'content', 'attribution',
                                       'eligibility'))
    chk('and MAY NOT answer "who is officially inactive"',
        not inactive['usable'])
    chk('refused on eligibility, by purpose, not by blanket state',
        inactive['failing_axes']['eligibility'].startswith(
            'NOT_AUTHORISED_FOR:'),
        str(inactive['failing_axes']))


def test_restricted_without_declared_purposes_refuses_everything():
    """A restriction nobody wrote down cannot be checked, so it blocks."""
    r = SV.new_report('x', transport=SV.PASS, content=SV.PASS,
                      eligibility={'state': SV.RESTRICTED, 'detail': 'vague'})
    u = SV.usable_for(r, 'anything', requires=('eligibility',))
    chk('an undeclared restriction refuses',
        u['failing_axes']['eligibility']
        == 'RESTRICTED_WITH_NO_DECLARED_PURPOSES')


def test_positive_observation_usable_negative_inference_refused():
    e = SV.espn_injuries_report(truncated=True, n_clubs=32,
                                n_clubs_at_cap=32, consumed=True)
    chk('completeness is PARTIAL on a fully capped feed',
        e['axes']['completeness']['state'] == SV.PARTIAL)
    chk('and says COVERAGE_NOT_ESTABLISHED / SUSPECTED_TRUNCATION',
        'SUSPECTED_TRUNCATION' in e['axes']['completeness']['detail'])

    positive = SV.usable_for(e, 'is this player listed OUT',
                             requires=('transport', 'content', 'attribution',
                                       'eligibility'))
    negative = SV.usable_for(e, 'who is NOT injured',
                             requires=('transport', 'content', 'completeness',
                                       'attribution', 'eligibility'))
    chk('the positive question is answerable', positive['usable'])
    chk('the negative question is refused', not negative['usable'])
    chk('and completeness is among its reasons',
        negative['failing_axes'].get('completeness') == SV.PARTIAL,
        str(negative['failing_axes']))

    whole = SV.espn_injuries_report(truncated=False, n_clubs=32,
                                    n_clubs_at_cap=3)
    chk('an uncapped capture passes completeness',
        whole['axes']['completeness']['state'] == SV.PASS)


def test_consumption_is_observed_not_implied():
    unread = SV.espn_injuries_report(truncated=False, consumed=False)
    chk('a source not observed to be read is NOT_ESTABLISHED on consumption',
        unread['axes']['consumption']['state'] == SV.NOT_ESTABLISHED)
    read = SV.espn_injuries_report(truncated=False, consumed=True)
    chk('and PASS only when observed',
        read['axes']['consumption']['state'] == SV.PASS)
    u = SV.usable_for(unread, 'is this player listed OUT',
                      requires=('transport', 'consumption'))
    chk('so six good axes do not imply the seventh', not u['usable'])


def test_a_missing_axis_raises_rather_than_being_assumed():
    r = {'source': 'x', 'axes': {'transport': {'state': SV.PASS}}}
    try:
        SV.usable_for(r, 'p', requires=('transport', 'content'))
        chk('a missing axis raises', False, 'it was assumed')
    except SV.ValidityError as e:
        chk('a missing axis raises', 'carries no' in str(e))


if __name__ == '__main__':
    for _n, _f in sorted((n, f) for n, f in list(globals().items())
                         if n.startswith('test_') and callable(f)):
        print(f'\n== {_n}')
        _f()
    print(f'\nPASSED {PASSED}  FAILED {FAILED}  BLOCKED {BLOCKED}')
    raise SystemExit(1 if FAILED else 0)
