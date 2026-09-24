"""Seven questions a source must answer separately, and one that cannot.

THE DEFECT THIS EXISTS TO END

`PASS` has meant at least four different things in this repository, and each
time it meant the wrong one something downstream believed a number it should
not have. Measured, all on 2026-09-24:

* `official_inactives` recorded **402 PASS rows**. 363 of 367 preserved blobs
  are the NFL.com page whose own visible text reads "Please check back soon
  for NFL Inactive Reports for this Season". The fetch worked; the page said
  it had nothing. That is TRANSPORT passing and CONTENT failing.
* `espn_injuries_json` returns exactly 25 entries per club in **20,736 of
  20,736** club-entries, with `"status": "success"` and no pagination
  metadata. Transport and content both pass; COMPLETENESS does not.
* The same feed is LEAGUE_WIDE. A capture covering all 32 clubs is not
  thereby a capture about this game, so ATTRIBUTION is its own question.
* `run_input.verify` reported a nine-day-old pin as `FRESH` because no age
  bound had been declared. FRESHNESS was never evaluated and the word said
  otherwise.
* `official_inactives` is authorised to answer "who is inactive" and is NOT
  authorised to answer "who is healthy". ELIGIBILITY is a per-purpose
  question, not a per-source one.
* And a source can satisfy all six and still never be read: the ATL @ GB run
  pinned seven families and the gadget layer consumed a candidate list that
  bypassed the availability filter. CONSUMPTION is observable and is not
  implied by the other six.

So seven axes, answered separately, never collapsed into one light.

THE AXIS THAT IS DELIBERATELY NOT HERE

There is no `TRUTH` axis. Nothing in this module asks whether the source is
RIGHT. A perfectly transported, content-bearing, complete, correctly
attributed, fresh, lawful and consumed source can still be wrong, and a
validity report that implied otherwise would be the most dangerous green light
of all.
"""
from __future__ import annotations

PASS = 'PASS'
FAIL = 'FAIL'
PARTIAL = 'PARTIAL'
RESTRICTED = 'RESTRICTED'
NOT_ESTABLISHED = 'NOT_ESTABLISHED'

#: The seven axes, in the order a failure makes the later ones unanswerable.
#: Content cannot be judged on bytes that never arrived; completeness cannot be
#: judged on a page with no content. The order is the dependency, not a
#: ranking of importance.
AXES = (
    ('transport', 'did the request succeed and preserve bytes'),
    ('content', 'do the preserved bytes carry the thing, not a shell or an '
                'empty-state page'),
    ('completeness', 'is the result whole, or truncated, paginated, capped or '
                     'partial'),
    ('attribution', 'does it belong to THIS game, team or player'),
    ('freshness', 'was it available before the forecast cut and recent enough '
                  'against a DECLARED bound'),
    ('eligibility', 'is this source lawful for THIS predictive purpose'),
    ('consumption', 'did the forecast actually read it'),
)

AXIS_NAMES = tuple(name for name, _ in AXES)

#: NOT_ESTABLISHED is the default for every axis. A source starts out having
#: proved nothing, and an axis nobody measured must never read PASS.
_DEFAULT = NOT_ESTABLISHED


class ValidityError(RuntimeError):
    """The report cannot be built. Distinct from a source failing an axis."""


def new_report(source: str, **axes) -> dict:
    """A validity report for one source. Unstated axes are NOT_ESTABLISHED."""
    if not source:
        raise ValidityError('a validity report needs a named source')
    bad = sorted(set(axes) - set(AXIS_NAMES))
    if bad:
        raise ValidityError(
            f'{bad} are not declared axes. The axis set is closed so that a '
            f'source cannot quietly grow a dimension nobody agreed to.')
    out = {'source': source,
           'axes': {name: dict(state=_DEFAULT, detail='') for name in AXIS_NAMES}}
    for name, value in axes.items():
        if isinstance(value, str):
            value = {'state': value, 'detail': ''}
        state = value.get('state')
        if state not in (PASS, FAIL, PARTIAL, RESTRICTED, NOT_ESTABLISHED):
            raise ValidityError(
                f'{source}.{name} was given state {state!r}, which is not one '
                f'of the declared states.')
        out['axes'][name] = {'state': state,
                             'detail': value.get('detail', ''),
                             **{k: v for k, v in value.items()
                                if k not in ('state', 'detail')}}
    return out


def usable_for(report: dict, purpose: str, *, requires=AXIS_NAMES) -> dict:
    """May this source answer `purpose`, and on which axes does it fail?

    `requires` is the axis set THIS purpose needs, declared by the caller. A
    source can be perfectly adequate for one question and refused for another:
    a truncated injury feed is usable for "is this player listed OUT" and
    refused for "who is not injured", and the difference is completeness.
    """
    axes = report.get('axes') or {}
    missing = [a for a in requires if a not in axes]
    if missing:
        raise ValidityError(f'{report.get("source")!r} carries no {missing}')
    failing = {}
    for a in requires:
        state = axes[a]['state']
        if a == 'eligibility' and state == RESTRICTED:
            # RESTRICTED IS NOT A POLITE FAIL. It means the source is lawful
            # for SOME purposes and not others, so the question is whether
            # THIS purpose is on the list. Treating it as a blanket failure
            # would collapse the eligibility axis back into a single light,
            # which is the exact defect this module exists to end -- and it
            # would refuse ESPN for "is this player listed OUT", which it is
            # authorised to answer.
            allowed = axes[a].get('authorised_for')
            if allowed is None:
                failing[a] = 'RESTRICTED_WITH_NO_DECLARED_PURPOSES'
            elif purpose not in allowed:
                failing[a] = f'NOT_AUTHORISED_FOR:{purpose}'
            continue
        if state in (FAIL, PARTIAL, NOT_ESTABLISHED):
            failing[a] = state
    return {
        'source': report.get('source'),
        'purpose': purpose,
        'required_axes': list(requires),
        'usable': not failing,
        'failing_axes': failing,
        'detail': ('every required axis passes' if not failing else
                   '; '.join(f'{a}={s}' for a, s in sorted(failing.items()))),
    }


def summarise(report: dict) -> str:
    src = report.get('source', '?')
    parts = [f'{a}: {report["axes"][a]["state"]}' for a in AXIS_NAMES]
    return f'{src}  ' + ' · '.join(parts)


# ---------------------------------------------------------------------------
# The three worked examples, kept in code rather than prose so they are run.
# ---------------------------------------------------------------------------

def espn_injuries_report(*, truncated: bool, n_clubs_at_cap=None,
                         n_clubs=None, consumed=None) -> dict:
    """The measured state of the ESPN injuries feed."""
    return new_report(
        'espn_injuries_json',
        transport={'state': PASS,
                   'detail': 'HTTP success and bytes preserved'},
        content={'state': PASS,
                 'detail': 'real designations for named athletes'},
        completeness={
            'state': PARTIAL if truncated else PASS,
            'detail': (
                'COVERAGE_NOT_ESTABLISHED / SUSPECTED_TRUNCATION: every club '
                'returned exactly the page cap and the response declares '
                'success with no pagination metadata'
                if truncated else 'at least one club returned under the cap'),
            'n_clubs': n_clubs, 'n_clubs_at_cap': n_clubs_at_cap},
        attribution={'state': PASS,
                     'detail': 'LEAGUE_WIDE, filtered to the game by club id'},
        eligibility={
            'state': RESTRICTED,
            'detail': (
                'authorised for injury DESIGNATIONS only. It carries no '
                'game-day-inactive value, so it may not answer "who is '
                'inactive", and absence from it is never evidence of health'),
            'authorised_for': ('is this player listed with an injury '
                               'designation',
                               'is this player listed OUT')},
        consumption=({'state': PASS if consumed else NOT_ESTABLISHED,
                      'detail': 'observed in the run input contract'}
                     if consumed is not None else NOT_ESTABLISHED))


def nfl_inactives_landing_report(empty_state: bool) -> dict:
    """The NFL.com /inactives/ landing page: transport PASS, content FAIL."""
    return new_report(
        'official_inactives',
        transport={'state': PASS,
                   'detail': 'HTTP 200 and ~400 KB preserved'},
        content={
            'state': FAIL if empty_state else PASS,
            'detail': ('the page states its own empty state -- "Please check '
                       'back soon for NFL Inactive Reports for this Season" '
                       '-- so the fetch succeeded and carried no list'
                       if empty_state else 'an inactive list is present')},
        completeness=NOT_ESTABLISHED,
        attribution=NOT_ESTABLISHED,
        eligibility={'state': RESTRICTED,
                     'detail': ('authorised for OFFICIAL_GAMEDAY_INACTIVE '
                                'only. Being unlisted here is not a claim '
                                'that a player is active.'),
                     'authorised_for': ('who is officially inactive',)},
        consumption=NOT_ESTABLISHED)
